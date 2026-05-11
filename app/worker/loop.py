import asyncio
import socket
from datetime import timedelta
from uuid import UUID

import structlog
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import Link, SpanKind, StatusCode

from app.core.telemetry import counter, histogram, updown
from app.db.models.job import Job, JobStatus
from app.db.models.job_log import JobLog
from app.db.session import AsyncSessionLocal
from app.queue.dequeue import dequeue_fifo, dequeue_priority, drain_retry_queue
from app.queue.enqueue import enqueue_priority, enqueue_retry
from app.services.retry_service import calculate_backoff_with_jitter
from app.utils.time import epoch_now, now_utc
from app.worker.executors.registry import get_executor

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer("jobqueue.worker")

_worker_id = socket.gethostname()


def _links_from_traceparent(traceparent: str | None) -> list[Link]:
    """Reconstruct an OTel Link from a W3C traceparent string stored in job payload."""
    if not traceparent:
        return []
    try:
        ctx = extract({"traceparent": traceparent})
        remote_span = trace.get_current_span(ctx)
        span_ctx = remote_span.get_span_context()
        if span_ctx.is_valid:
            return [Link(context=span_ctx)]
    except Exception:
        pass
    return []


async def _add_log(session, job_id: UUID, level: str, message: str) -> None:
    session.add(JobLog(job_id=job_id, level=level, message=message))


async def handle_failure(job_id: str, error_message: str, redis) -> None:
    # Called while already inside a job.execute span — child spans created here
    # are automatically parented to it via OTel context propagation.
    with tracer.start_as_current_span("job.handle_failure") as fail_span:
        fail_span.set_attribute("job.id", job_id)
        fail_span.set_attribute("error.message", error_message[:256])

        async with AsyncSessionLocal() as session:
            job = await session.get(Job, UUID(job_id))
            if job is None:
                return

            job.error = error_message
            await _add_log(session, job.id, "error", f"Attempt {job.attempts} failed: {error_message}")

            if job.attempts >= job.max_attempts:
                job.status = JobStatus.FAILED.value
                job.completed_at = now_utc()
                await _add_log(
                    session, job.id, "error",
                    f"Max attempts ({job.max_attempts}) reached. Job permanently failed."
                )
                fail_span.set_attribute("retry.scheduled", False)
                fail_span.set_status(StatusCode.ERROR, error_message[:256])
                if c := counter("jobs_failed"):
                    c.add(1, {
                        "job_type": job.type,
                        "priority": job.priority,
                        "failure_reason": "max_attempts_exhausted",
                    })
                if g := updown("jobs_active"):
                    g.add(-1, {"job_type": job.type})
                logger.error(
                    "job_permanently_failed",
                    job_id=job_id,
                    attempts=job.attempts,
                    error=error_message,
                )
            else:
                delay = calculate_backoff_with_jitter(job.attempts)
                job.status = JobStatus.QUEUED.value
                job.next_retry_at = now_utc() + timedelta(seconds=delay)
                retry_at = epoch_now() + delay

                with tracer.start_as_current_span("queue.enqueue_retry") as retry_span:
                    retry_span.set_attribute("job.id", job_id)
                    retry_span.set_attribute("retry.delay_seconds", round(delay, 2))
                    retry_span.set_attribute("retry.run_at_epoch", retry_at)
                    await enqueue_retry(redis, job_id, retry_at)

                await _add_log(
                    session, job.id, "warning",
                    f"Scheduled retry in {delay:.1f}s (attempt {job.attempts}/{job.max_attempts})"
                )
                fail_span.set_attribute("retry.scheduled", True)
                fail_span.set_attribute("retry.delay_seconds", round(delay, 2))
                fail_span.set_attribute("retry.attempt_number", job.attempts)
                if c := counter("jobs_retried"):
                    c.add(1, {
                        "job_type": job.type,
                        "priority": job.priority,
                        "attempt_number": str(job.attempts),
                    })
                if h := histogram("retry_backoff"):
                    h.record(delay, {"job_type": job.type, "attempt_number": str(job.attempts)})
                if g := updown("jobs_active"):
                    g.add(-1, {"job_type": job.type})
                logger.warning(
                    "job_retry_scheduled",
                    job_id=job_id,
                    delay_seconds=round(delay, 2),
                    attempt=job.attempts,
                    max_attempts=job.max_attempts,
                )

            await session.commit()


async def worker_loop(redis) -> None:
    logger.info("worker_loop_started")
    while True:
        try:
            due = await drain_retry_queue(redis)
            for jid in due:
                async with AsyncSessionLocal() as session:
                    job = await session.get(Job, UUID(jid))
                    if job and job.status == JobStatus.QUEUED.value:
                        await enqueue_priority(redis, jid, job.priority)
                        logger.debug("retry_job_requeued", job_id=jid)

            job_id = await dequeue_priority(redis)
            source = "priority"
            if not job_id:
                job_id = await dequeue_fifo(redis, timeout=1)
                source = "fifo"

            if not job_id:
                if c := counter("worker_loop_iterations"):
                    c.add(1, {"worker_id": _worker_id, "outcome": "no_job"})
                continue

            structlog.contextvars.bind_contextvars(job_id=job_id)
            try:
                # ── Phase 1: fetch job and mark PROCESSING ────────────────────
                async with AsyncSessionLocal() as session:
                    job = await session.get(Job, UUID(job_id))
                    if job is None:
                        logger.warning("job_not_found_in_db", job_id=job_id)
                        continue
                    if job.status != JobStatus.QUEUED.value:
                        logger.warning(
                            "job_status_not_queued",
                            job_id=job_id,
                            status=job.status,
                        )
                        continue

                    structlog.contextvars.bind_contextvars(
                        job_type=job.type,
                        job_priority=job.priority,
                    )

                    traceparent = (job.payload or {}).get("_otel_traceparent")

                    job.status = JobStatus.PROCESSING.value
                    job.started_at = now_utc()
                    job.attempts += 1
                    await _add_log(
                        session, job.id, "info",
                        f"Starting executor '{job.type}' (attempt {job.attempts}/{job.max_attempts}) from {source} queue"
                    )
                    await session.commit()

                    executor_type = job.type
                    payload = job.payload
                    created_at = job.created_at
                    started_at = job.started_at
                    attempt = job.attempts
                    max_attempts = job.max_attempts
                    job_priority = job.priority

                wait_seconds = (started_at - created_at).total_seconds()
                links = _links_from_traceparent(traceparent)

                # ── Phase 2: execute inside a linked root span ────────────────
                with tracer.start_as_current_span(
                    "job.execute",
                    links=links,
                    kind=SpanKind.CONSUMER,
                ) as exec_span:
                    exec_span.set_attribute("job.id", job_id)
                    exec_span.set_attribute("job.type", executor_type)
                    exec_span.set_attribute("job.priority", job_priority)
                    exec_span.set_attribute("job.attempt_number", attempt)
                    exec_span.set_attribute("job.max_attempts", max_attempts)
                    exec_span.set_attribute("job.queue_source", source)
                    exec_span.set_attribute("job.wait_seconds", round(wait_seconds, 3))
                    exec_span.set_attribute("worker.id", _worker_id)

                    if h := histogram("job_wait_duration"):
                        h.record(wait_seconds, {"job_type": executor_type, "priority": job_priority})
                    if g := updown("jobs_active"):
                        g.add(1, {"job_type": executor_type})

                    log_level = "info" if attempt == 1 else "warning"
                    getattr(logger, log_level)(
                        "job_execution_started",
                        job_id=job_id,
                        job_type=executor_type,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        queue_source=source,
                        wait_seconds=round(wait_seconds, 3),
                    )

                    executor = get_executor(executor_type)
                    t_start = now_utc()

                    try:
                        with tracer.start_as_current_span(
                            f"executor.{executor_type}",
                            kind=SpanKind.INTERNAL,
                        ) as exe_span:
                            exe_span.set_attribute("job.id", job_id)
                            exe_span.set_attribute("executor.timeout_seconds", executor.max_execution_seconds)
                            result = await asyncio.wait_for(
                                executor.execute(job_id=job_id, payload=payload),
                                timeout=executor.max_execution_seconds,
                            )
                            exe_span.set_attribute("executor.outcome", "success")

                        duration_s = (now_utc() - t_start).total_seconds()
                        if h := histogram("job_processing_duration"):
                            h.record(duration_s, {"job_type": executor_type, "priority": job_priority})
                        if h := histogram("worker_executor_duration"):
                            h.record(duration_s, {"job_type": executor_type, "worker_id": _worker_id})

                        async with AsyncSessionLocal() as session:
                            job = await session.get(Job, UUID(job_id))
                            if job is None:
                                continue
                            if job.status == JobStatus.CANCELLED.value:
                                logger.info("job_cancelled_during_execution", job_id=job_id)
                                if g := updown("jobs_active"):
                                    g.add(-1, {"job_type": executor_type})
                                continue
                            job.status = JobStatus.COMPLETED.value
                            job.completed_at = now_utc()
                            job.result = result
                            job.error = None
                            await _add_log(session, job.id, "info", f"Completed successfully. Result: {result}")
                            await session.commit()

                        exec_span.set_attribute("job.outcome", "completed")
                        if c := counter("jobs_completed"):
                            c.add(1, {"job_type": executor_type, "priority": job_priority})
                        if g := updown("jobs_active"):
                            g.add(-1, {"job_type": executor_type})
                        if c := counter("worker_loop_iterations"):
                            c.add(1, {"worker_id": _worker_id, "outcome": "job_processed"})

                        logger.info(
                            "job_completed",
                            job_id=job_id,
                            job_type=executor_type,
                            duration_ms=round(duration_s * 1000, 2),
                        )

                    except asyncio.TimeoutError:
                        duration_s = (now_utc() - t_start).total_seconds()
                        exec_span.set_status(StatusCode.ERROR, "execution timed out")
                        exec_span.set_attribute("job.outcome", "timeout")
                        if h := histogram("job_processing_duration"):
                            h.record(duration_s, {"job_type": executor_type, "priority": job_priority})
                        if c := counter("jobs_failed"):
                            c.add(1, {
                                "job_type": executor_type,
                                "priority": job_priority,
                                "failure_reason": "timeout",
                            })
                        logger.error(
                            "job_timed_out",
                            job_id=job_id,
                            job_type=executor_type,
                            timeout_seconds=executor.max_execution_seconds,
                        )
                        await handle_failure(
                            job_id,
                            f"Execution timed out after {executor.max_execution_seconds}s",
                            redis,
                        )

                    except Exception as exc:
                        duration_s = (now_utc() - t_start).total_seconds()
                        exec_span.set_status(StatusCode.ERROR, str(exc)[:256])
                        exec_span.set_attribute("job.outcome", "error")
                        exec_span.set_attribute("error.type", type(exc).__name__)
                        if h := histogram("job_processing_duration"):
                            h.record(duration_s, {"job_type": executor_type, "priority": job_priority})
                        if c := counter("jobs_failed"):
                            c.add(1, {
                                "job_type": executor_type,
                                "priority": job_priority,
                                "failure_reason": "executor_error",
                            })
                        logger.error(
                            "job_execution_error",
                            job_id=job_id,
                            job_type=executor_type,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                        await handle_failure(job_id, str(exc), redis)

            finally:
                structlog.contextvars.unbind_contextvars("job_id", "job_type", "job_priority")

        except Exception as outer:
            if c := counter("worker_loop_iterations"):
                c.add(1, {"worker_id": _worker_id, "outcome": "error"})
            logger.exception("worker_loop_unexpected_error", error=str(outer))
            await asyncio.sleep(1)
