import time

from app.db.models.job import JobPriority

FIFO_KEY = "queue:fifo"
PRIORITY_KEY = "queue:priority"
RETRY_KEY = "queue:retry"

_PRIORITY_WEIGHTS: dict[str, float] = {
    JobPriority.HIGH.value: 0.0,
    JobPriority.MEDIUM.value: 1000.0,
    JobPriority.LOW.value: 2000.0,
}


def priority_score(priority: str) -> float:
    weight = _PRIORITY_WEIGHTS.get(priority, 1000.0)
    return weight + (time.time() / 1e12)
