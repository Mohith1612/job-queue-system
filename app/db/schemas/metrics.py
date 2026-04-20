from pydantic import BaseModel


class QueueDepths(BaseModel):
    fifo: int
    priority: int
    retry: int


class MetricsRead(BaseModel):
    counts_by_status: dict[str, int]
    avg_processing_time_seconds: float | None
    queue_depths: QueueDepths
