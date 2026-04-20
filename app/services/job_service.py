import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job import Job, JobStatus
from app.db.models.job_log import JobLog
from app.db.schemas.job import JobCreate, JobListResponse, JobRead, JobDetail
from app.queue.client import get_redis_pool
from app.queue.enqueue import remove_from_queues
from app.services.idempotency import get_or_create_job

logger = logging.getLogger(__name__)


async def create_job(session: AsyncSession, job_create: JobCreate) -> tuple[Job, bool]:
    return await get_or_create_job(session, job_create)


async def list_jobs(
    session: AsyncSession,
    status: str | None = None,
    type_: str | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> JobListResponse:
    query = select(Job)
    if status:
        query = query.where(Job.status == status)
    if type_:
        query = query.where(Job.type == type_)
    if priority:
        query = query.where(Job.priority == priority)

    count_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Job.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    jobs = list(result.scalars().all())

    return JobListResponse(
        items=[JobRead.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_job(session: AsyncSession, job_id: UUID) -> JobDetail | None:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    logs_result = await session.execute(
        select(JobLog)
        .where(JobLog.job_id == job_id)
        .order_by(JobLog.created_at.asc())
    )
    logs = list(logs_result.scalars().all())
    return JobDetail.model_validate({"job": job, "logs": logs})


async def cancel_job(session: AsyncSession, job_id: UUID) -> Job | None:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    cancellable = {JobStatus.QUEUED.value, JobStatus.PROCESSING.value}
    if job.status not in cancellable:
        return job

    job.status = JobStatus.CANCELLED.value
    redis = get_redis_pool()
    await remove_from_queues(redis, str(job_id))
    await session.commit()
    logger.info("cancelled job %s", job_id)
    return job
