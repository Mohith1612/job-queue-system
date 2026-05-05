from app.db.models.job import Job, JobStatus
from app.queue.keys import FIFO_KEY, PRIORITY_KEY, RETRY_KEY
from app.utils.time import now_utc


async def _completed_job(db_session, started_offset_s: float = 2.0):
    """Insert a completed job with a known processing duration."""
    from datetime import timedelta

    job = Job(type="email_send", payload={}, priority="medium", max_attempts=3)
    job.status = JobStatus.COMPLETED.value
    job.started_at = now_utc()
    job.completed_at = job.started_at + timedelta(seconds=started_offset_s)
    db_session.add(job)
    await db_session.commit()
    return job


# --- GET /api/v1/metrics ---

async def test_metrics_returns_correct_shape(client):
    resp = await client.get("/api/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()

    assert "counts_by_status" in data
    assert "avg_processing_time_seconds" in data
    assert "queue_depths" in data

    counts = data["counts_by_status"]
    for status in ("queued", "processing", "completed", "failed", "cancelled"):
        assert status in counts


async def test_metrics_counts_empty_db(client):
    resp = await client.get("/api/v1/metrics")
    data = resp.json()
    assert all(v == 0 for v in data["counts_by_status"].values())
    assert data["avg_processing_time_seconds"] is None


async def test_metrics_counts_reflect_db_state(client, db_session, fake_redis):
    from tests.integration.test_jobs_api import _make_job

    await _make_job(db_session, fake_redis, status=JobStatus.QUEUED.value)
    await _make_job(db_session, fake_redis, status=JobStatus.QUEUED.value)
    await _make_job(db_session, fake_redis, status=JobStatus.COMPLETED.value)
    await _make_job(db_session, fake_redis, status=JobStatus.FAILED.value)

    resp = await client.get("/api/v1/metrics")
    counts = resp.json()["counts_by_status"]
    assert counts["queued"] == 2
    assert counts["completed"] == 1
    assert counts["failed"] == 1
    assert counts["processing"] == 0


async def test_metrics_avg_processing_time(client, db_session):
    await _completed_job(db_session, started_offset_s=4.0)
    await _completed_job(db_session, started_offset_s=2.0)

    resp = await client.get("/api/v1/metrics")
    avg = resp.json()["avg_processing_time_seconds"]
    assert avg is not None
    # avg of 4s and 2s = 3s, allow small float variance
    assert abs(avg - 3.0) < 0.1


async def test_metrics_queue_depths(client, fake_redis):
    await fake_redis.lpush(FIFO_KEY, "job-a")
    await fake_redis.zadd(PRIORITY_KEY, {"job-b": 0.5, "job-c": 1.5})
    await fake_redis.zadd(RETRY_KEY, {"job-d": 9999999999.0})

    resp = await client.get("/api/v1/metrics")
    depths = resp.json()["queue_depths"]
    assert depths["fifo"] == 1
    assert depths["priority"] == 2
    assert depths["retry"] == 1
