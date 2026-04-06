from fastapi import APIRouter

router = APIRouter()

# Routes are registered in their respective modules and imported here
from app.api.v1 import jobs, metrics  # noqa: E402, F401

router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
