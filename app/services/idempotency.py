import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telemetry import counter
from app.db.models.job import Job
from app.db.schemas.job import JobCreate
from app.queue.client import get_redis_pool
from app.queue.enqueue import enqueue_priority

logger = structlog.get_logger(__name__)


async def get_or_create_job(
    session: AsyncSession, job_create: JobCreate
) -> tuple[Job, bool]:
    """Return (job, is_new). is_new=False means the idempotency key was a hit."""
    if job_create.idempotency_key:
        existing = await session.execute(
            select(Job).where(Job.idempotency_key == job_create.idempotency_key)
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            if c := counter("idempotency_hits"):
                c.add(1, {"job_type": row.type})
            logger.debug(
                "idempotency_hit",
                idempotency_key=job_create.idempotency_key,
                job_id=str(row.id),
            )
            return row, False

    job = Job(
        type=job_create.type,
        payload=job_create.payload,
        priority=job_create.priority,
        idempotency_key=job_create.idempotency_key,
        max_attempts=job_create.max_attempts,
    )
    session.add(job)

    try:
        await session.flush()
        redis = get_redis_pool()
        await enqueue_priority(redis, str(job.id), job.priority)
        await session.commit()

        if c := counter("jobs_created"):
            c.add(1, {"job_type": job.type, "priority": job.priority})

        logger.info(
            "job_created",
            job_id=str(job.id),
            job_type=job.type,
            priority=job.priority,
        )
        return job, True

    except IntegrityError:
        await session.rollback()
        existing = await session.execute(
            select(Job).where(Job.idempotency_key == job_create.idempotency_key)
        )
        row = existing.scalar_one()
        if c := counter("idempotency_hits"):
            c.add(1, {"job_type": row.type})
        logger.debug(
            "idempotency_hit_race",
            idempotency_key=job_create.idempotency_key,
            job_id=str(row.id),
        )
        return row, False
