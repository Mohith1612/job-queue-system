import asyncio
import signal
import socket

import structlog

from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal, get_engine
from app.queue.client import close_redis_pool, get_redis_pool
from app.worker.loop import worker_loop
from app.worker.recovery import run_startup_recovery

logger = structlog.get_logger(__name__)

_shutdown = asyncio.Event()


def _handle_sigterm(*_):
    logger.info("sigterm_received", event="sigterm_received")
    _shutdown.set()


async def main() -> None:
    configure_logging()

    worker_id = socket.gethostname()
    structlog.contextvars.bind_contextvars(worker_id=worker_id)

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    redis = get_redis_pool()

    async with AsyncSessionLocal() as session:
        await run_startup_recovery(session, redis)

    logger.info("worker_started", worker_id=worker_id)
    try:
        await worker_loop(redis)
    finally:
        await close_redis_pool()
        await get_engine().dispose()
        logger.info("worker_stopped", worker_id=worker_id)


if __name__ == "__main__":
    asyncio.run(main())
