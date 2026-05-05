from unittest.mock import patch

from app.queue.keys import priority_score


def test_priority_ordering():
    with patch("app.queue.keys.time") as mock_time:
        mock_time.time.return_value = 0.0
        high = priority_score("high")
        medium = priority_score("medium")
        low = priority_score("low")

    assert high < medium < low
    assert high == 0.0
    assert medium == 1000.0
    assert low == 2000.0


def test_fifo_within_same_tier():
    # Earlier timestamp → lower score → dequeued first via ZPOPMIN
    with patch("app.queue.keys.time") as mock_time:
        mock_time.time.return_value = 1_000_000_000.0
        score_first = priority_score("medium")
        mock_time.time.return_value = 2_000_000_000.0
        score_second = priority_score("medium")

    assert score_first < score_second


def test_unknown_priority_defaults_to_medium_weight():
    with patch("app.queue.keys.time") as mock_time:
        mock_time.time.return_value = 0.0
        score = priority_score("nonexistent")

    assert score == 1000.0


def test_high_always_beats_low():
    # Even with max plausible time difference, high score < low score
    with patch("app.queue.keys.time") as mock_time:
        mock_time.time.return_value = 9_999_999_999_999.0  # far future
        high = priority_score("high")
        mock_time.time.return_value = 0.0
        low = priority_score("low")

    # high weight=0, low weight=2000; time fraction is tiny so high still < low
    assert high < low
