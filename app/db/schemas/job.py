from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.job import JobPriority, JobStatus


class JobCreate(BaseModel):
    type: str
    payload: dict = {}
    priority: str = JobPriority.MEDIUM.value
    idempotency_key: str | None = None
    max_attempts: int = Field(default=5, ge=1, le=10)


class JobLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    level: str
    message: str
    created_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    payload: dict
    priority: str
    status: str
    idempotency_key: str | None
    attempts: int
    max_attempts: int
    next_retry_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    result: dict | None


class JobDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    payload: dict
    priority: str
    status: str
    idempotency_key: str | None
    attempts: int
    max_attempts: int
    next_retry_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    result: dict | None
    logs: list[JobLogRead] = []

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict) and "job" in obj:
            job = obj["job"]
            logs = obj.get("logs", [])
            data = {col.key: getattr(job, col.key) for col in job.__table__.columns}
            data["logs"] = [JobLogRead.model_validate(log) for log in logs]
            return cls(**data)
        return super().model_validate(obj, **kwargs)


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
    page: int
    page_size: int
