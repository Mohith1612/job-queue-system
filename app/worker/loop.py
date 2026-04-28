import asyncio
import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.db.models.job import Job, JobStatus
from app.db.models.job_log import JobLog
from app.db.session import AsyncSessionLocal
from app.queue.dequeue import dequeue_fifo, dequeue_priority, drain_retry_queue
from app.queue.enqueue import enqueue_priority, enqueue_retry
from app.queue.keys import priority_score
from app.services.retry_service import calculate_backoff_with_jitter
from app.utils.time import epoch_now, now_utc
from app.worker.executors.registry import get_executor

logger = logging.getLogger(__name__)


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
            logger.warning("job %s permanently failed after %d attempts", job_id, job.attempts)
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
            logger.info("job %s scheduled for retry in %.1fs", job_id, delay)

        await session.commit()


async def worker_loop(redis) -> None:
    logger.info("worker loop started")
    while True:
        try:
            due = await drain_retry_queue(redis)
            for job_id in due:
                async with AsyncSessionLocal() as session:
                    job = await session.get(Job, UUID(job_id))
                    if job and job.status == JobStatus.QUEUED.value:
                        score = priority_score(job.priority)
                        await enqueue_priority(redis, job_id, job.priority)
                        logger.debug("moved retry job %s back to priority queue", job_id)

            job_id = await dequeue_priority(redis)
            source = "priority"
            if not job_id:
                job_id = await dequeue_fifo(redis, timeout=1)
                source = "fifo"

            if not job_id:
                continue

            async with AsyncSessionLocal() as session:
                job = await session.get(Job, UUID(job_id))
                if job is None:
                    logger.warning("dequeued job %s not found in DB, skipping", job_id)
                    continue
                if job.status != JobStatus.QUEUED.value:
                    logger.warning("job %s status=%s (not queued), skipping", job_id, job.status)
                    continue

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
                max_attempts = job.max_attempts

            logger.info("executing job %s type=%s attempt=%d", job_id, executor_type, job.attempts if False else "?")

            executor = get_executor(executor_type)
            try:
                result = await asyncio.wait_for(
                    executor.execute(job_id=job_id, payload=payload),
                    timeout=executor.max_execution_seconds,
                )
                async with AsyncSessionLocal() as session:
                    job = await session.get(Job, UUID(job_id))
                    if job is None:
                        continue
                    if job.status == JobStatus.CANCELLED.value:
                        logger.info("job %s was cancelled during execution, discarding result", job_id)
                        continue
                    job.status = JobStatus.COMPLETED.value
                    job.completed_at = now_utc()
                    job.result = result
                    job.error = None
                    await _add_log(session, job.id, "info", f"Completed successfully. Result: {result}")
                    await session.commit()
                logger.info("job %s completed", job_id)

            except asyncio.TimeoutError:
                await handle_failure(job_id, f"Execution timed out after {executor.max_execution_seconds}s", redis)
            except Exception as exc:
                await handle_failure(job_id, str(exc), redis)

        except Exception as outer:
            logger.exception("unexpected error in worker loop: %s", outer)
            await asyncio.sleep(1)
