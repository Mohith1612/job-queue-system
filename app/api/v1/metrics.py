import logging

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.db.models.job import Job, JobStatus
from app.db.schemas.metrics import MetricsRead, QueueDepths
from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=MetricsRead)
async def get_metrics(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    status_counts: dict[str, int] = {s.value: 0 for s in JobStatus}
    rows = await session.execute(
        select(Job.status, func.count().label("n")).group_by(Job.status)
    )
    for status, count in rows:
        status_counts[status] = count

    avg_result = await session.execute(
        text(
            "SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) "
            "FROM jobs WHERE status = 'completed' "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL"
        )
    )
    avg_seconds: float | None = avg_result.scalar_one_or_none()

    fifo_depth = await redis.llen(FIFO_KEY)
    priority_depth = await redis.zcard(PRIORITY_KEY)
    retry_depth = await redis.zcard(RETRY_KEY)

    return MetricsRead(
        counts_by_status=status_counts,
        avg_processing_time_seconds=float(avg_seconds) if avg_seconds is not None else None,
        queue_depths=QueueDepths(fifo=fifo_depth, priority=priority_depth, retry=retry_depth),
    )
