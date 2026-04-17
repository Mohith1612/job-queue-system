from redis.asyncio import Redis

from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY, priority_score


async def enqueue_priority(redis: Redis, job_id: str, priority: str) -> None:
    score = priority_score(priority)
    await redis.zadd(PRIORITY_KEY, {job_id: score})


async def enqueue_fifo(redis: Redis, job_id: str) -> None:
    await redis.lpush(FIFO_KEY, job_id)


async def enqueue_retry(redis: Redis, job_id: str, run_at_epoch: float) -> None:
    await redis.zadd(RETRY_KEY, {job_id: run_at_epoch})


async def remove_from_queues(redis: Redis, job_id: str) -> None:
    await redis.lrem(FIFO_KEY, 0, job_id)
    await redis.zrem(PRIORITY_KEY, job_id)
    await redis.zrem(RETRY_KEY, job_id)
