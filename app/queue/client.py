from redis.asyncio import Redis, ConnectionPool

from app.core.config import get_settings

_pool: ConnectionPool | None = None


def get_redis_pool() -> Redis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return Redis(connection_pool=_pool)


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
