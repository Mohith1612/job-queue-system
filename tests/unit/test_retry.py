from unittest.mock import patch

from app.services.retry_service import calculate_backoff_with_jitter


def test_backoff_is_positive():
    for attempt in range(10):
        assert calculate_backoff_with_jitter(attempt) > 0


def test_backoff_multiplier_range():
    # base * (0.5 + random()), random() in [0,1) → multiplier in [0.5, 1.5)
    for attempt in range(1, 6):
        base = min(2 ** attempt, 3600)
        for _ in range(50):
            result = calculate_backoff_with_jitter(attempt)
            assert base * 0.5 <= result < base * 1.5


def test_backoff_respects_max_delay():
    # With max_delay=10, large attempt still caps base at 10
    for _ in range(50):
        result = calculate_backoff_with_jitter(20, max_delay=10)
        assert 5.0 <= result < 15.0


def test_backoff_grows_with_attempts():
    with patch("app.services.retry_service.random") as mock_rng:
        mock_rng.random.return_value = 0.5  # multiplier = 1.0
        assert calculate_backoff_with_jitter(1) == 2.0
        assert calculate_backoff_with_jitter(2) == 4.0
        assert calculate_backoff_with_jitter(3) == 8.0
        assert calculate_backoff_with_jitter(4) == 16.0
