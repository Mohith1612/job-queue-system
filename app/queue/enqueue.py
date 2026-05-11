import time

from redis.asyncio import Redis

from app.core.telemetry import counter, histogram
from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY, priority_score


async def enqueue_priority(redis: Redis, job_id: str, priority: str, job_type: str = "") -> None:
    score = priority_score(priority)
    t = time.perf_counter()
    await redis.zadd(PRIORITY_KEY, {job_id: score})
    if h := histogram("redis_command_duration"):
        h.record(time.perf_counter() - t, {"command": "zadd"})
    if c := counter("enqueue"):
        c.add(1, {"queue_name": "priority", "job_type": job_type, "priority": priority})


async def enqueue_fifo(redis: Redis, job_id: str, job_type: str = "") -> None:
    t = time.perf_counter()
    await redis.lpush(FIFO_KEY, job_id)
    if h := histogram("redis_command_duration"):
        h.record(time.perf_counter() - t, {"command": "lpush"})
    if c := counter("enqueue"):
        c.add(1, {"queue_name": "fifo", "job_type": job_type, "priority": ""})


async def enqueue_retry(redis: Redis, job_id: str, run_at_epoch: float, job_type: str = "") -> None:
    t = time.perf_counter()
    await redis.zadd(RETRY_KEY, {job_id: run_at_epoch})
    if h := histogram("redis_command_duration"):
        h.record(time.perf_counter() - t, {"command": "zadd"})


async def remove_from_queues(redis: Redis, job_id: str) -> None:
    await redis.lrem(FIFO_KEY, 0, job_id)
    await redis.zrem(PRIORITY_KEY, job_id)
    await redis.zrem(RETRY_KEY, job_id)
