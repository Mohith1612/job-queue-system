import uuid

import pytest

from app.db.models.job import Job, JobStatus
from app.queue.keys import PRIORITY_KEY
from app.utils.time import now_utc


# --- helpers ---

async def _make_job(db_session, fake_redis, *, type="email_send", priority="medium", status=None):
    """Insert a job directly into the test DB, enqueue if queued."""
    from app.queue.enqueue import enqueue_priority

    job = Job(type=type, payload={"test": True}, priority=priority, max_attempts=3)
    if status:
        job.status = status
    if status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
        job.started_at = now_utc()
        job.completed_at = now_utc()
    db_session.add(job)
    await db_session.commit()

    if job.status == JobStatus.QUEUED.value:
        await enqueue_priority(fake_redis, str(job.id), job.priority)

    return job


# --- health ---

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- POST /api/v1/jobs ---

async def test_create_job_returns_201(client):
    resp = await client.post("/api/v1/jobs", json={
        "type": "email_send",
        "payload": {"to": "a@b.com"},
        "priority": "high",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "email_send"
    assert data["priority"] == "high"
    assert data["status"] == "queued"
    assert data["attempts"] == 0
    assert "id" in data


async def test_create_job_enqueued_in_redis(client, fake_redis):
    await client.post("/api/v1/jobs", json={"type": "email_send", "payload": {}})
    assert await fake_redis.zcard(PRIORITY_KEY) == 1


async def test_create_job_idempotency_new_key_is_201(client):
    resp = await client.post("/api/v1/jobs", json={
        "type": "email_send",
        "payload": {},
        "idempotency_key": "unique-key-1",
    })
    assert resp.status_code == 201
    assert "X-Idempotency-Replay" not in resp.headers


async def test_create_job_idempotency_replay_is_200(client):
    first = await client.post("/api/v1/jobs", json={
        "type": "email_send",
        "payload": {},
        "idempotency_key": "replay-key",
    })
    second = await client.post("/api/v1/jobs", json={
        "type": "email_send",
        "payload": {},
        "idempotency_key": "replay-key",
    })
    assert second.status_code == 200
    assert second.headers.get("X-Idempotency-Replay") == "true"
    assert first.json()["id"] == second.json()["id"]


async def test_create_job_invalid_type_returns_422(client):
    resp = await client.post("/api/v1/jobs", json={"type": "nonexistent", "payload": {}})
    assert resp.status_code == 422


async def test_create_job_invalid_priority_returns_422(client):
    resp = await client.post("/api/v1/jobs", json={"type": "email_send", "payload": {}, "priority": "urgent"})
    assert resp.status_code == 422


# --- GET /api/v1/jobs ---

async def test_list_jobs_empty(client):
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1


async def test_list_jobs_returns_created(client):
    await client.post("/api/v1/jobs", json={"type": "email_send", "payload": {}})
    await client.post("/api/v1/jobs", json={"type": "payment_retry", "payload": {}})

    resp = await client.get("/api/v1/jobs")
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_list_jobs_filter_by_status(client, db_session, fake_redis):
    await _make_job(db_session, fake_redis, status=JobStatus.COMPLETED.value)
    await _make_job(db_session, fake_redis, status=JobStatus.QUEUED.value)

    resp = await client.get("/api/v1/jobs?status=completed")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "completed"


async def test_list_jobs_filter_by_type(client, db_session, fake_redis):
    await _make_job(db_session, fake_redis, type="email_send")
    await _make_job(db_session, fake_redis, type="payment_retry")

    resp = await client.get("/api/v1/jobs?type=email_send")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["type"] == "email_send"


async def test_list_jobs_filter_by_priority(client, db_session, fake_redis):
    await _make_job(db_session, fake_redis, priority="high")
    await _make_job(db_session, fake_redis, priority="low")

    resp = await client.get("/api/v1/jobs?priority=high")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["priority"] == "high"


async def test_list_jobs_pagination(client, db_session, fake_redis):
    for _ in range(5):
        await _make_job(db_session, fake_redis)

    resp = await client.get("/api/v1/jobs?page=1&page_size=2")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


async def test_list_jobs_invalid_status_returns_422(client):
    resp = await client.get("/api/v1/jobs?status=unknown")
    assert resp.status_code == 422


# --- GET /api/v1/jobs/{id} ---

async def test_get_job_detail(client, db_session, fake_redis):
    job = await _make_job(db_session, fake_redis)

    resp = await client.get(f"/api/v1/jobs/{job.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(job.id)
    assert data["type"] == job.type
    assert "logs" in data
    assert isinstance(data["logs"], list)


async def test_get_job_not_found_returns_404(client):
    resp = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- POST /api/v1/jobs/{id}/cancel ---

async def test_cancel_queued_job(client, db_session, fake_redis):
    job = await _make_job(db_session, fake_redis)

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_cancel_completed_job_returns_409(client, db_session, fake_redis):
    job = await _make_job(db_session, fake_redis, status=JobStatus.COMPLETED.value)

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == 409
    assert "completed" in resp.json()["detail"]


async def test_cancel_nonexistent_job_returns_404(client):
    resp = await client.post(f"/api/v1/jobs/{uuid.uuid4()}/cancel")
    assert resp.status_code == 404


async def test_cancel_removes_from_redis(client, db_session, fake_redis):
    job = await _make_job(db_session, fake_redis)
    assert await fake_redis.zcard(PRIORITY_KEY) == 1

    await client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert await fake_redis.zcard(PRIORITY_KEY) == 0
