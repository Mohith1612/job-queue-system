import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.models.job import JobStatus
from app.db.schemas.job import JobCreate, JobDetail, JobListResponse, JobRead
from app.main import limiter
from app.services.job_service import cancel_job, create_job, get_job, list_jobs
from app.worker.executors.registry import EXECUTOR_REGISTRY

_RATE_LIMIT = f"{get_settings().rate_limit_per_minute}/minute"

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_TYPES = set(EXECUTOR_REGISTRY.keys())
VALID_STATUSES = {s.value for s in JobStatus}
VALID_PRIORITIES = {"high", "medium", "low"}


@router.post("", response_model=JobRead, status_code=201)
@limiter.limit(_RATE_LIMIT)
async def create_job_endpoint(
    request: Request,
    body: JobCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    if body.type not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown job type '{body.type}'. Valid types: {sorted(VALID_TYPES)}",
        )
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid priority '{body.priority}'. Must be one of: high, medium, low",
        )

    job, is_new = await create_job(session, body)

    if not is_new:
        response.status_code = 200
        response.headers["X-Idempotency-Replay"] = "true"

    return JobRead.model_validate(job)


@router.get("", response_model=JobListResponse)
async def list_jobs_endpoint(
    status: str | None = Query(default=None),
    type: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{status}'")
    if priority and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"Invalid priority '{priority}'")

    return await list_jobs(session, status=status, type_=type, priority=priority, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job_endpoint(
    job_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job_endpoint(
    job_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    job = await cancel_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    cancellable = {JobStatus.QUEUED.value, JobStatus.PROCESSING.value, JobStatus.CANCELLED.value}
    if job.status not in cancellable:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in status '{job.status}'",
        )

    return JobRead.model_validate(job)
