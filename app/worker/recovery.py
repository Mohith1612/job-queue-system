from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.telemetry import counter
from app.db.models.job import Job, JobStatus
from app.db.models.job_log import JobLog
from app.queue.enqueue import enqueue_retry
from app.services.retry_service import calculate_backoff_with_jitter
from app.utils.time import epoch_now, now_utc

logger = structlog.get_logger(__name__)


async def run_startup_recovery(session: AsyncSession, redis) -> None:
    settings = get_settings()
    threshold = now_utc() - timedelta(minutes=settings.recovery_stuck_threshold_minutes)

    result = await session.execute(
        select(Job)
        .where(Job.status == JobStatus.PROCESSING.value)
        .where(Job.started_at < threshold)
    )
    stuck_jobs = list(result.scalars().all())

    if not stuck_jobs:
        logger.info("startup_recovery_clean", stuck_jobs=0)
        return

    logger.warning("startup_recovery_started", stuck_jobs=len(stuck_jobs))

    for job in stuck_jobs:
        job.attempts += 1
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED.value
            job.completed_at = now_utc()
            job.error = "Worker crashed; max attempts exhausted during recovery"
            session.add(
                JobLog(
                    job_id=job.id,
                    level="error",
                    message=f"Permanently failed during startup recovery after {job.attempts} attempts",
                )
            )
            if c := counter("worker_recovery_actions"):
                c.add(1, {"action": "failed_terminal"})
            logger.warning(
                "recovery_job_failed_terminal",
                job_id=str(job.id),
                attempts=job.attempts,
            )
        else:
            delay = calculate_backoff_with_jitter(job.attempts)
            job.status = JobStatus.QUEUED.value
            job.next_retry_at = now_utc() + timedelta(seconds=delay)
            retry_at = epoch_now() + delay
            await enqueue_retry(redis, str(job.id), retry_at)
            session.add(
                JobLog(
                    job_id=job.id,
                    level="warning",
                    message=f"Re-queued by startup recovery (was stuck in processing). Retry in {delay:.1f}s",
                )
            )
            if c := counter("worker_recovery_actions"):
                c.add(1, {"action": "requeued"})
            logger.info(
                "recovery_job_requeued",
                job_id=str(job.id),
                delay_seconds=round(delay, 2),
            )

    await session.commit()
    logger.info("startup_recovery_complete", stuck_jobs=len(stuck_jobs))
