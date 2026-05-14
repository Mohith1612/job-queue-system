"""OTel SDK setup: TracerProvider, MeterProvider, and all custom metric instruments."""
import threading
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import AggregationTemporality
from opentelemetry.sdk.metrics.view import (
    ExplicitBucketHistogramAggregation,
    View,
)
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_initialized = False

# ── gauge state updated by background polling tasks ──────────────────────────
_gauge_state: dict[str, dict[str, float]] = {
    "queue_depth": {},
    "db_pool_size": {},
    "redis_pool_connections": {},
}

# ── metric instruments (populated by setup_telemetry) ─────────────────────────
_counters: dict[str, Any] = {}
_histograms: dict[str, Any] = {}
_gauges: dict[str, Any] = {}


def counter(name: str):
    return _counters.get(name)


def histogram(name: str):
    return _histograms.get(name)


def updown(name: str):
    return _gauges.get(name)


def set_gauge(metric: str, attrs: dict, value: float) -> None:
    _gauge_state[metric][str(sorted(attrs.items()))] = (value, attrs)


def _make_queue_depth_callback():
    def cb(_options):
        from opentelemetry.metrics import Observation
        for _, (val, attrs) in _gauge_state["queue_depth"].items():
            yield Observation(val, attrs)
    return cb


def _make_db_pool_callback():
    def cb(_options):
        from opentelemetry.metrics import Observation
        for _, (val, attrs) in _gauge_state["db_pool_size"].items():
            yield Observation(val, attrs)
    return cb


def _make_redis_pool_callback():
    def cb(_options):
        from opentelemetry.metrics import Observation
        for _, (val, attrs) in _gauge_state["redis_pool_connections"].items():
            yield Observation(val, attrs)
    return cb


_HISTOGRAM_VIEWS = [
    View(
        instrument_name="jobqueue_job_wait_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            [0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600, 1800]
        ),
    ),
    View(
        instrument_name="jobqueue_job_processing_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            [0.1, 0.5, 1, 5, 10, 30, 60, 120, 300]
        ),
    ),
    View(
        instrument_name="jobqueue_worker_executor_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            [0.1, 0.5, 1, 5, 10, 30, 60, 120, 300]
        ),
    ),
    View(
        instrument_name="jobqueue_retry_backoff_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 3600]
        ),
    ),
    View(
        instrument_name="jobqueue_db_query_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1]
        ),
    ),
    View(
        instrument_name="jobqueue_redis_command_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            [0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
        ),
    ),
]


def setup_telemetry(service_name: str, otlp_endpoint: str | None = None) -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: "0.1.0",
    })

    # ── TracerProvider ────────────────────────────────────────────────────────
    tracer_provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    trace.set_tracer_provider(tracer_provider)

    # ── MeterProvider ─────────────────────────────────────────────────────────
    prom_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[prom_reader],
        views=_HISTOGRAM_VIEWS,
    )
    metrics.set_meter_provider(meter_provider)

    # ── Auto-instrumentation ──────────────────────────────────────────────────
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    RedisInstrumentor().instrument()

    # ── Meter and custom instruments ──────────────────────────────────────────
    meter = metrics.get_meter("jobqueue", version="0.1.0")

    for name, desc in [
        ("jobs_created", "Total jobs created"),
        ("jobs_completed", "Total jobs completed successfully"),
        ("jobs_failed", "Total jobs permanently failed"),
        ("jobs_retried", "Total retry attempts scheduled"),
        ("jobs_cancelled", "Total jobs cancelled"),
        ("idempotency_hits", "Total idempotency key hits (replays)"),
        ("rate_limit_hits", "Total rate limit rejections"),
        ("enqueue", "Total enqueue operations"),
        ("dequeue", "Total dequeue operations"),
        ("retry_drain", "Total jobs drained from the retry sorted set"),
        ("worker_loop_iterations", "Total worker loop iterations"),
        ("worker_idle_seconds", "Accumulated idle time in the worker loop"),
        ("worker_recovery_actions", "Recovery actions taken at worker startup"),
        ("worker_restarts", "Worker process starts"),
        ("db_errors", "Total database errors by type"),
        ("redis_errors", "Total Redis errors by command and type"),
    ]:
        _counters[name] = meter.create_counter(f"jobqueue_{name}_total", description=desc)

    for name, unit, desc in [
        ("job_wait_duration", "s", "Time a job spent waiting in queue before execution"),
        ("job_processing_duration", "s", "Job execution wall-clock time"),
        ("worker_executor_duration", "s", "Duration of executor.execute() calls"),
        ("retry_backoff", "s", "Backoff delay calculated per retry"),
        ("db_query_duration", "s", "Database query duration by operation"),
        ("redis_command_duration", "s", "Redis command duration by command type"),
    ]:
        _histograms[name] = meter.create_histogram(
            f"jobqueue_{name}_seconds", unit=unit, description=desc
        )

    _gauges["jobs_active"] = meter.create_up_down_counter(
        "jobqueue_jobs_active",
        description="Jobs currently in PROCESSING state",
    )

    meter.create_observable_gauge(
        "jobqueue_queue_depth",
        callbacks=[_make_queue_depth_callback()],
        description="Current depth of each Redis queue",
    )
    meter.create_observable_gauge(
        "jobqueue_db_pool_size",
        callbacks=[_make_db_pool_callback()],
        description="Database connection pool size by state",
    )
    meter.create_observable_gauge(
        "jobqueue_redis_pool_connections",
        callbacks=[_make_redis_pool_callback()],
        description="Redis connection pool size by state",
    )


def setup_fastapi_instrumentation(app) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)


def setup_sqlalchemy_instrumentation(engine) -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def start_worker_metrics_server(port: int) -> None:
    from prometheus_client import start_http_server
    t = threading.Thread(
        target=start_http_server,
        args=(port,),
        daemon=True,
        name="metrics-server",
    )
    t.start()
