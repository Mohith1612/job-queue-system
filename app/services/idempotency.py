import structlog
from opentelemetry import trace
from opentelemetry.propagate import inject
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telemetry import counter
from app.db.models.job import Job
from app.db.schemas.job import JobCreate
from app.queue.client import get_redis_pool
from app.queue.enqueue import enqueue_priority

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer("jobqueue.api")


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

    # Capture current trace context so the worker can link back to this span.
    carrier: dict[str, str] = {}
    inject(carrier)

    payload_with_trace = {
        **(job_create.payload or {}),
        "_otel_traceparent": carrier.get("traceparent"),
    }

    job = Job(
        type=job_create.type,
        payload=payload_with_trace,
        priority=job_create.priority,
        idempotency_key=job_create.idempotency_key,
        max_attempts=job_create.max_attempts,
    )
    session.add(job)

    with tracer.start_as_current_span("job.create") as job_span:
        try:
            await session.flush()  # job.id is now assigned

            job_span.set_attribute("job.id", str(job.id))
            job_span.set_attribute("job.type", job.type)
            job_span.set_attribute("job.priority", job.priority)
            job_span.set_attribute("job.is_new", True)
            job_span.set_attribute("job.max_attempts", job.max_attempts)

            redis = get_redis_pool()
            with tracer.start_as_current_span("queue.enqueue") as enq_span:
                enq_span.set_attribute("queue.name", "priority")
                enq_span.set_attribute("job.id", str(job.id))
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
            job_span.set_attribute("job.is_new", False)
            job_span.set_attribute("job.id", str(row.id))
            if c := counter("idempotency_hits"):
                c.add(1, {"job_type": row.type})
            logger.debug(
                "idempotency_hit_race",
                idempotency_key=job_create.idempotency_key,
                job_id=str(row.id),
            )
            return row, False
