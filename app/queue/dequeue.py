import time

from redis.asyncio import Redis

from app.core.telemetry import counter, histogram
from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY
from app.utils.time import epoch_now


async def dequeue_priority(redis: Redis) -> str | None:
    t = time.perf_counter()
    result = await redis.zpopmin(PRIORITY_KEY, 1)
    if h := histogram("redis_command_duration"):
        h.record(time.perf_counter() - t, {"command": "zpopmin"})
    if result:
        return result[0][0]
    return None


async def dequeue_fifo(redis: Redis, timeout: int = 1) -> str | None:
    t = time.perf_counter()
    result = await redis.brpop(FIFO_KEY, timeout=timeout)
    if h := histogram("redis_command_duration"):
        h.record(time.perf_counter() - t, {"command": "brpop"})
    if result:
        return result[1]
    return None


async def drain_retry_queue(redis: Redis, limit: int = 10) -> list[str]:
    now = epoch_now()
    t = time.perf_counter()
    due: list[str] = await redis.zrangebyscore(RETRY_KEY, min="-inf", max=now, start=0, num=limit)
    if h := histogram("redis_command_duration"):
        h.record(time.perf_counter() - t, {"command": "zrangebyscore"})

    claimed = []
    for job_id in due:
        removed = await redis.zrem(RETRY_KEY, job_id)
        if removed:
            claimed.append(job_id)

    if claimed:
        if c := counter("retry_drain"):
            c.add(len(claimed))

    return claimed
