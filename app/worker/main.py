import asyncio
import signal
import socket

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.telemetry import (
    counter,
    set_gauge,
    setup_sqlalchemy_instrumentation,
    setup_telemetry,
    start_worker_metrics_server,
)
from app.db.session import AsyncSessionLocal, get_engine
from app.queue.client import close_redis_pool, get_redis_pool
from app.worker.loop import worker_loop
from app.worker.recovery import run_startup_recovery

logger = structlog.get_logger(__name__)

_shutdown = asyncio.Event()


def _handle_sigterm(*_):
    logger.info("sigterm_received")
    _shutdown.set()


async def _poll_queues_and_pools(redis, interval: int = 15) -> None:
    from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY
    while True:
        try:
            set_gauge("queue_depth", {"queue_name": "priority"}, float(await redis.zcard(PRIORITY_KEY)))
            set_gauge("queue_depth", {"queue_name": "fifo"}, float(await redis.llen(FIFO_KEY)))
            set_gauge("queue_depth", {"queue_name": "retry"}, float(await redis.zcard(RETRY_KEY)))
        except Exception:
            pass
        try:
            pool = get_engine().pool
            set_gauge("db_pool_size", {"state": "checked_out"}, float(pool.checked_out()))
            set_gauge("db_pool_size", {"state": "checked_in"}, float(pool.checkedin()))
            set_gauge("db_pool_size", {"state": "overflow"}, float(max(pool.overflow(), 0)))
        except Exception:
            pass
        await asyncio.sleep(interval)


async def main() -> None:
    configure_logging()
    settings = get_settings()

    worker_id = socket.gethostname()
    structlog.contextvars.bind_contextvars(worker_id=worker_id)

    setup_telemetry(
        service_name=f"{settings.otel_service_name}-worker",
        otlp_endpoint=settings.otel_endpoint,
    )
    start_worker_metrics_server(settings.metrics_port)

    engine = get_engine()
    setup_sqlalchemy_instrumentation(engine)

    if c := counter("worker_restarts"):
        c.add(1, {"worker_id": worker_id})

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    redis = get_redis_pool()

    async with AsyncSessionLocal() as session:
        await run_startup_recovery(session, redis)

    poll_task = asyncio.create_task(_poll_queues_and_pools(redis))

    logger.info("worker_started", worker_id=worker_id)
    try:
        await worker_loop(redis)
    finally:
        poll_task.cancel()
        await close_redis_pool()
        await engine.dispose()
        logger.info("worker_stopped", worker_id=worker_id)


if __name__ == "__main__":
    asyncio.run(main())
