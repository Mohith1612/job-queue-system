import random


def calculate_backoff_with_jitter(attempt: int, max_delay: int = 3600) -> float:
    base = min(2 ** attempt, max_delay)
    return base * (0.5 + random.random())
