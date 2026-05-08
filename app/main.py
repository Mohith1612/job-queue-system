import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.telemetry import (
    set_gauge,
    setup_fastapi_instrumentation,
    setup_sqlalchemy_instrumentation,
    setup_telemetry,
)
from app.db.session import get_engine
from app.middleware.logging import RequestIDMiddleware
from app.queue.client import get_redis_pool

logger = structlog.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)


async def _poll_queue_depths(redis, interval: int = 15) -> None:
    """Background task: update queue-depth observable gauges every interval seconds."""
    from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY
    while True:
        try:
            priority_depth = await redis.zcard(PRIORITY_KEY)
            fifo_depth = await redis.llen(FIFO_KEY)
            retry_depth = await redis.zcard(RETRY_KEY)
            set_gauge("queue_depth", {"queue_name": "priority"}, float(priority_depth))
            set_gauge("queue_depth", {"queue_name": "fifo"}, float(fifo_depth))
            set_gauge("queue_depth", {"queue_name": "retry"}, float(retry_depth))
        except Exception:
            pass
        await asyncio.sleep(interval)


async def _poll_db_pool(interval: int = 15) -> None:
    """Background task: update DB connection pool gauges every interval seconds."""
    while True:
        try:
            engine = get_engine()
            pool = engine.pool
            checked_out = pool.checked_out()
            checked_in = pool.checkedin()
            overflow = pool.overflow()
            set_gauge("db_pool_size", {"state": "checked_out"}, float(checked_out))
            set_gauge("db_pool_size", {"state": "checked_in"}, float(checked_in))
            set_gauge("db_pool_size", {"state": "overflow"}, float(max(overflow, 0)))
        except Exception:
            pass
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()

    setup_telemetry(
        service_name=f"{settings.otel_service_name}-api",
        otlp_endpoint=settings.otel_endpoint,
    )

    engine = get_engine()
    setup_sqlalchemy_instrumentation(engine)

    redis = get_redis_pool()

    depth_task = asyncio.create_task(_poll_queue_depths(redis))
    pool_task = asyncio.create_task(_poll_db_pool())

    logger.info("api_started")
    yield

    depth_task.cancel()
    pool_task.cancel()
    await engine.dispose()
    logger.info("api_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Job Queue System", version="0.1.0", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.router import router
    app.include_router(router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    setup_fastapi_instrumentation(app)
    return app


app = create_app()
