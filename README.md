# Job Queue System

A distributed job queue system with priority scheduling, automatic retries, and idempotency. Built with FastAPI, PostgreSQL, Redis, and React.

**Live:** [queue.mohith16.com](https://queue.mohith16.com) · API: [queue-api.mohith16.com](https://queue-api.mohith16.com)

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Job Types](#job-types)
- [Queue Design](#queue-design)
- [Worker](#worker)
- [Retry Logic](#retry-logic)
- [Idempotency](#idempotency)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Load Testing](#load-testing)
- [Deployment](#deployment)
- [CI/CD](#cicd)

---

## Overview

The system accepts jobs via a REST API, queues them in Redis with priority ordering, and processes them asynchronously via a background worker. Jobs are persisted in PostgreSQL throughout their lifecycle. Failed jobs are automatically retried with exponential backoff. A React dashboard provides visibility into job state, logs, and queue metrics.

**Key features:**

- Priority-based job scheduling (high / medium / low) with FIFO fairness within each priority level
- Automatic retries with exponential backoff and jitter (configurable per job, up to 10 attempts)
- Idempotency keys to safely deduplicate retried API requests
- Per-job execution timeout enforcement
- Startup recovery for jobs that were processing when a worker crashed
- Full execution logs per job
- System metrics endpoint (queue depths, counts by status, avg processing time)
- Rate limiting on the create endpoint (10 req/min per IP, configurable)
- Web dashboard for creating, viewing, filtering, and cancelling jobs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.111+, Uvicorn, Python 3.11+ |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| Queue | Redis 7 |
| Worker | Python asyncio |
| Rate Limiting | slowapi |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Tailwind CSS, Recharts |
| Containers | Docker, Docker Compose |
| CI/CD | GitHub Actions → GHCR → Oracle VM (ARM64) |

---

## Architecture

```
                    ┌─────────────────┐
                    │   React Frontend │
                    │  (Cloudflare Pages) │
                    └────────┬────────┘
                             │ HTTPS
                    ┌────────▼────────┐
                    │   nginx (TLS)   │
                    └────────┬────────┘
                             │ HTTP
                    ┌────────▼────────┐
                    │   FastAPI (API) │
                    └───┬─────────┬──┘
                        │         │
              ┌─────────▼──┐  ┌───▼──────────┐
              │ PostgreSQL  │  │    Redis      │
              │  (jobs,     │  │  (3 queues)   │
              │   logs)     │  │               │
              └─────────────┘  └───────┬───────┘
                                       │
                              ┌────────▼────────┐
                              │     Worker      │
                              │ (async loop,    │
                              │  executors)     │
                              └─────────────────┘
```

**Queue flow:**

1. API receives `POST /api/v1/jobs`, validates, persists to PostgreSQL with status `queued`, pushes job ID to Redis priority queue
2. Worker dequeues job ID from Redis, fetches full job from PostgreSQL, executes via registered executor
3. On success: updates status to `completed`, stores result
4. On failure: calculates backoff delay, schedules retry via Redis retry queue, re-queues when due

---

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Run locally

```bash
git clone https://github.com/mohith1612/job-queue-system
cd job-queue-system
cp .env.example .env
docker compose up
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Migrations run automatically on API startup via Alembic.

### Run without Docker

```bash
# Start dependencies
docker compose up postgres redis -d

# Install Python dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload

# Start worker (separate terminal)
python -m app.worker.main

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

---

## Configuration

All settings are read from environment variables (or a `.env` file). See `.env.example` for a template.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://jobqueue:jobqueue@localhost:5432/jobqueue` | PostgreSQL async connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `WORKER_CONCURRENCY` | `4` | Worker concurrency setting (scale by running multiple worker containers) |
| `JOB_MAX_EXECUTION_SECONDS` | `300` | Global job execution timeout (overridden per executor) |
| `RECOVERY_STUCK_THRESHOLD_MINUTES` | `10` | Jobs stuck in `processing` longer than this are recovered on worker startup |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed CORS origins |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max `POST /api/v1/jobs` requests per minute per IP |

---

## API Reference

Base URL: `/api/v1`

### Create Job

```
POST /api/v1/jobs
```

Rate limited: 10 requests/minute per IP.

**Request body:**

```json
{
  "type": "email_send",
  "payload": { "to": "user@example.com", "subject": "Hello" },
  "priority": "high",
  "idempotency_key": "optional-unique-string",
  "max_attempts": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Job type. One of: `email_send`, `payment_retry`, `report_generate` |
| `payload` | object | No | Arbitrary JSON passed to the executor |
| `priority` | string | No | `high`, `medium` (default), or `low` |
| `idempotency_key` | string | No | If provided, duplicate requests return the existing job |
| `max_attempts` | int | No | 1–10, default 5 |

**Responses:**

- `201 Created` — new job created
- `200 OK` + `X-Idempotency-Replay: true` header — existing job returned (idempotency replay)
- `422 Unprocessable Entity` — invalid `type` or `priority`
- `429 Too Many Requests` — rate limit exceeded

---

### List Jobs

```
GET /api/v1/jobs
```

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter: `queued`, `processing`, `completed`, `failed`, `cancelled` |
| `type` | string | Filter: `email_send`, `payment_retry`, `report_generate` |
| `priority` | string | Filter: `high`, `medium`, `low` |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Results per page, 1–100 (default: 20) |

**Response:**

```json
{
  "items": [ /* array of job objects */ ],
  "total": 142,
  "page": 1,
  "page_size": 20
}
```

---

### Get Job

```
GET /api/v1/jobs/{job_id}
```

Returns the full job object plus execution logs.

**Response:**

```json
{
  "id": "uuid",
  "type": "email_send",
  "payload": {},
  "priority": "high",
  "status": "completed",
  "idempotency_key": null,
  "attempts": 1,
  "max_attempts": 5,
  "next_retry_at": null,
  "created_at": "2026-05-07T10:00:00Z",
  "started_at": "2026-05-07T10:00:01Z",
  "completed_at": "2026-05-07T10:00:03Z",
  "error": null,
  "result": { "message_id": "msg_abc123", "delivered": true },
  "logs": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "level": "info",
      "message": "Executing email_send job",
      "created_at": "2026-05-07T10:00:01Z"
    }
  ]
}
```

---

### Cancel Job

```
POST /api/v1/jobs/{job_id}/cancel
```

Cancels a job if it is in `queued` or `processing` status.

- `200 OK` — job cancelled
- `404 Not Found` — job does not exist
- `409 Conflict` — job is `completed` or `failed` and cannot be cancelled

---

### Get Metrics

```
GET /api/v1/metrics
```

**Response:**

```json
{
  "counts_by_status": {
    "queued": 5,
    "processing": 2,
    "completed": 150,
    "failed": 3,
    "cancelled": 1
  },
  "avg_processing_time_seconds": 12.5,
  "queue_depths": {
    "fifo": 0,
    "priority": 5,
    "retry": 2
  }
}
```

---

### Health Check

```
GET /health
```

Returns `{"status": "ok"}`. Used by Docker healthchecks and deployment scripts.

---

## Job Types

Three executors are built in. All simulate realistic async workloads.

### `email_send`

Simulates sending an email via SMTP.

- **Timeout:** 30 seconds
- **Simulated failure rate:** 10%
- **Payload example:** `{"to": "user@example.com", "subject": "...", "body": "..."}`
- **Result example:** `{"message_id": "msg_abc123", "delivered": true, "recipient": "user@example.com"}`

### `payment_retry`

Simulates a payment gateway call with transient failures.

- **Timeout:** 60 seconds
- **Simulated failure rate:** 30% (models gateway unavailability)
- **Payload example:** `{"amount": 99.99, "account_id": "acct_xyz", "currency": "USD"}`
- **Result example:** `{"transaction_id": "txn_xyz", "status": "approved", "amount": 99.99}`

### `report_generate`

Simulates a CPU/IO-bound report generation task (runs in thread executor).

- **Timeout:** 120 seconds
- **Payload example:** `{"report_type": "monthly_sales", "format": "pdf", "date_range": "2026-01"}`
- **Result example:** `{"rows": 1234, "format": "pdf", "size_bytes": 250000, "report_id": "rpt_12345"}`

### Adding a custom executor

```python
# app/worker/executors/my_executor.py
from app.worker.executors.base import BaseExecutor

class MyExecutor(BaseExecutor):
    max_execution_seconds = 45

    async def execute(self, job_id: str, payload: dict) -> dict:
        # your logic here
        return {"result": "done"}
```

```python
# app/worker/executors/registry.py
from app.worker.executors.my_executor import MyExecutor

EXECUTOR_REGISTRY = {
    "email_send": EmailExecutor(),
    "payment_retry": PaymentExecutor(),
    "report_generate": ReportExecutor(),
    "my_custom_type": MyExecutor(),   # add here
}
```

The new type is immediately available in the API and validated on job creation.

---

## Queue Design

Redis holds three queues. The worker drains them in priority order on every loop iteration.

### Priority Queue (`queue:priority`)

A Redis sorted set. Score encodes both priority and insertion time:

```
score = priority_weight + (unix_timestamp / 1e12)

HIGH   → weight 0.0
MEDIUM → weight 1000.0
LOW    → weight 2000.0
```

Lower score = dequeued first. The fractional timestamp provides FIFO ordering within the same priority level. Dequeued via `ZPOPMIN`.

### FIFO Queue (`queue:fifo`)

A Redis list. Used as a fallback when the priority queue is empty. Enqueued via `LPUSH`, dequeued via `BRPOP` with a 1-second timeout.

### Retry Queue (`queue:retry`)

A Redis sorted set where the score is the Unix timestamp at which the job becomes eligible for retry. Each worker loop iteration drains jobs with `score ≤ now` and re-enqueues them to the priority queue.

---

## Worker

The worker runs as a separate process (or container) with a continuous async event loop.

### Startup sequence

1. Configure logging
2. Register `SIGTERM` / `SIGINT` handlers for graceful shutdown
3. Initialise Redis connection pool
4. **Startup recovery:** scan for jobs stuck in `processing` status longer than `RECOVERY_STUCK_THRESHOLD_MINUTES` — re-queue or mark failed

### Main loop (each iteration)

1. Drain retry queue — move due jobs back to priority queue
2. `ZPOPMIN` from priority queue (non-blocking)
3. If empty, `BRPOP` from FIFO queue (1-second block)
4. If no job available, loop again
5. Fetch job from PostgreSQL, verify status is still `queued`
6. Mark `processing`, record `started_at`, increment `attempts`
7. Execute via registered executor with `asyncio.wait_for(timeout=...)`
8. On success → `completed`, store result
9. On failure → `handle_failure()` → schedule retry or mark `failed`
10. On cancellation detected mid-execution → discard, log

### Scaling

The worker processes one job at a time. To increase throughput, run multiple worker containers — each one will independently dequeue and execute jobs.

```yaml
# docker-compose.yml
worker:
  deploy:
    replicas: 4
```

---

## Retry Logic

Failed jobs are retried with **exponential backoff and random jitter**:

```
delay = 2^attempt × random(0.5, 1.5)   capped at 3600 seconds (1 hour)
```

| Attempt | Base delay | With jitter (approx) |
|---------|-----------|----------------------|
| 1 | 2s | 1–3s |
| 2 | 4s | 2–6s |
| 3 | 8s | 4–12s |
| 4 | 16s | 8–24s |
| 5 (final) | — | marked `failed` |

When `attempts >= max_attempts` the job is marked `failed` and not retried. The `max_attempts` value is set per job at creation time (default 5, range 1–10).

---

## Idempotency

Supply an `idempotency_key` in the create request to make it safe to retry:

```bash
curl -X POST /api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "payment_retry",
    "payload": {"amount": 99.99},
    "idempotency_key": "payment-order-7842-attempt-1"
  }'
```

- **First call:** creates the job, returns `201`
- **Subsequent calls with the same key:** returns the existing job with `200` and header `X-Idempotency-Replay: true`
- **Concurrent calls with the same key:** safe — handled via database unique constraint and retry-on-conflict

---

## Project Structure

```
job-queue-system/
├── app/
│   ├── main.py                        # App factory, CORS, rate limiter setup
│   ├── core/
│   │   ├── config.py                  # Settings (pydantic-settings)
│   │   └── logging.py
│   ├── api/
│   │   └── v1/
│   │       ├── jobs.py                # Job endpoints
│   │       └── metrics.py             # Metrics endpoint
│   ├── db/
│   │   ├── models/
│   │   │   ├── job.py                 # Job ORM model
│   │   │   └── job_log.py             # Execution log ORM model
│   │   └── schemas/
│   │       ├── job.py                 # Pydantic request/response schemas
│   │       └── metrics.py
│   ├── queue/
│   │   ├── client.py                  # Redis connection pool
│   │   ├── keys.py                    # Key naming and priority score calc
│   │   ├── enqueue.py                 # Push to priority / FIFO / retry queues
│   │   └── dequeue.py                 # Pop from priority → FIFO → retry queues
│   ├── services/
│   │   ├── job_service.py             # Business logic (create, list, get, cancel)
│   │   ├── idempotency.py             # Idempotency key lookup and dedup
│   │   └── retry_service.py           # Backoff calculation
│   └── worker/
│       ├── main.py                    # Entry point, signal handling
│       ├── loop.py                    # Main event loop
│       ├── recovery.py                # Startup recovery for stuck jobs
│       └── executors/
│           ├── base.py                # BaseExecutor abstract class
│           ├── registry.py            # Executor registry
│           ├── email_send.py
│           ├── payment_retry.py
│           └── report_generate.py
├── frontend/
│   └── src/
│       ├── pages/                     # Home, Dashboard, CreateJob, JobDetail, Metrics
│       ├── api/                       # Axios client and job API functions
│       └── types/
├── migrations/                        # Alembic migration files
├── tests/
│   ├── unit/                          # Unit tests (retry, priority, executors)
│   └── integration/                   # Integration tests (API endpoints, DB)
├── k6/                                # Load test scripts and report
│   ├── helpers.js
│   ├── smoke.js
│   ├── load.js
│   ├── stress.js
│   ├── soak.js
│   ├── cancel.js
│   ├── spike.js
│   ├── idempotency.js
│   ├── breakpoint.js
│   ├── rate_limit.js
│   └── REPORT.md
├── vm/                                # Production deployment files
│   ├── docker-compose.yml
│   ├── nginx/conf.d/job-queue.conf
│   └── README.md
├── docker-compose.yml                 # Local development
├── Dockerfile.api
├── Dockerfile.worker
└── pyproject.toml
```

---

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires PostgreSQL)
TEST_DATABASE_URL=postgresql+asyncpg://jobqueue:jobqueue@localhost/jobqueue_test \
  pytest tests/integration/ -v --cov=app
```

The CI pipeline runs both test suites on every push and pull request, with a PostgreSQL service container for integration tests.

---

## Load Testing

K6 load tests live in `k6/`. See [`k6/REPORT.md`](k6/REPORT.md) for full results.

| Test | VUs | p(95) | Error rate | Notes |
|------|-----|-------|------------|-------|
| Smoke | 1 | 429ms | 0% | Baseline |
| Idempotency | 10 | 231ms | 0% | 2,923 requests, all replay headers correct |
| Cancel | 30 | 242ms | 0% | 409 conflicts handled cleanly |
| Load | 20 | 266ms | 0% | 9 min sustained |
| Spike (30× burst) | 150 | 612ms | 0% | Two sudden bursts |
| Breakpoint | 200 | 864ms | 0% | Ceiling not found |

Zero errors across ~273,000 total requests. The read-path ceiling was not reached at 200 VUs.

**Worker stress test** (`worker_stress.js`) runs three concurrent scenarios — a job creation flood (70% `payment_retry`), a queue depth monitor, and a completion tracker measuring end-to-end retry latency. Custom metrics: `retry_latency_ms`, `queue_depth_samples`, `job_eventually_completed`. See [`k6/REPORT.md`](k6/REPORT.md) for full details.

**Run a test:**

```bash
k6 run --env BASE_URL=https://queue-api.mohith16.com k6/smoke.js
```

**Before running write-heavy tests**, raise the rate limit via `RATE_LIMIT_PER_MINUTE` on the server (see `k6/REPORT.md` for the full procedure).

---

## Deployment

Production runs on an Oracle VM (ARM64) behind nginx. The `vm/` directory contains all server-side configuration files.

### First-time server setup

See [`vm/README.md`](vm/README.md) for the complete setup guide. Summary:

```bash
# Copy config files to VM
scp vm/docker-compose.yml appuser@<VM_IP>:/opt/job-queue-system/
scp vm/nginx/conf.d/job-queue.conf appuser@<VM_IP>:/opt/proxy/nginx/conf.d/

# On the VM
cd /opt/job-queue-system
cp .env.example .env   # fill in credentials
docker compose pull
docker compose up -d

# Reload nginx
docker exec proxy_nginx nginx -s reload
```

### Infrastructure layout on VM

```
/opt/
├── proxy/                 ← shared nginx + certbot (handles TLS for all projects)
│   └── nginx/conf.d/
│       └── job-queue.conf
└── job-queue-system/
    ├── docker-compose.yml
    └── .env
```

**Networking:**
- `postgres` and `redis` are on an internal-only Docker network — not reachable from outside
- `api` is on both the internal network and the shared `proxy` network so nginx can reach it
- `worker` is on the internal network only

### Run on Kubernetes (kind)

The `k8s/` directory has a minimal single-node setup for running the backend on a local Kubernetes cluster via [kind](https://kind.sigs.k8s.io/). It's intended as a learning/portfolio exercise — one replica of everything, ephemeral Postgres storage, dev secret in the repo. See [`k8s/README.md`](k8s/README.md) for the walkthrough.

---

## CI/CD

Every push to `main` triggers a four-stage pipeline:

```
security audit → quality (lint/test/build) → docker build + push → deploy
```

| Stage | What it does |
|-------|-------------|
| **security** | `pip-audit` on Python deps, `npm audit` on frontend |
| **quality** | Unit + integration tests with coverage, TypeScript typecheck, frontend build |
| **docker-build** | Builds `linux/arm64` images for API and Worker, pushes to GHCR |
| **deploy-backend** | SSH into Oracle VM, `docker compose pull && docker compose up -d --force-recreate` |

**Required GitHub secrets:**

| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | Oracle VM IP address |
| `DEPLOY_USER` | SSH username (e.g. `appuser`) |
| `DEPLOY_SSH_KEY` | Private SSH key |

Docker images are published to:
- `ghcr.io/mohith1612/job-queue-system/api:latest`
- `ghcr.io/mohith1612/job-queue-system/worker:latest`
