import asyncio
import socket
from datetime import timedelta
from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.telemetry import counter, histogram, updown
from app.db.models.job import Job, JobStatus
from app.db.models.job_log import JobLog
from app.db.session import AsyncSessionLocal
from app.queue.dequeue import dequeue_fifo, dequeue_priority, drain_retry_queue
from app.queue.enqueue import enqueue_priority, enqueue_retry
from app.queue.keys import priority_score
from app.services.retry_service import calculate_backoff_with_jitter
from app.utils.time import epoch_now, now_utc
from app.worker.executors.registry import get_executor

logger = structlog.get_logger(__name__)

_worker_id = socket.gethostname()


async def _add_log(session, job_id: UUID, level: str, message: str) -> None:
    session.add(JobLog(job_id=job_id, level=level, message=message))


async def handle_failure(job_id: str, error_message: str, redis) -> None:
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
            await enqueue_retry(redis, job_id, retry_at)
            await _add_log(
                session, job.id, "warning",
                f"Scheduled retry in {delay:.1f}s (attempt {job.attempts}/{job.max_attempts})"
            )
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
                    result = await asyncio.wait_for(
                        executor.execute(job_id=job_id, payload=payload),
                        timeout=executor.max_execution_seconds,
                    )
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
