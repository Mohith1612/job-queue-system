import time
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def epoch_now() -> float:
    return time.time()
