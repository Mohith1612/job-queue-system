from app.worker.executors.base import BaseExecutor
from app.worker.executors.email_send import EmailExecutor
from app.worker.executors.payment_retry import PaymentExecutor
from app.worker.executors.report_generate import ReportExecutor

EXECUTOR_REGISTRY: dict[str, type[BaseExecutor]] = {
    "email_send": EmailExecutor,
    "payment_retry": PaymentExecutor,
    "report_generate": ReportExecutor,
}


def get_executor(job_type: str) -> BaseExecutor:
    cls = EXECUTOR_REGISTRY.get(job_type)
    if cls is None:
        raise ValueError(
            f"Unknown job type: {job_type!r}. Valid types: {list(EXECUTOR_REGISTRY.keys())}"
        )
    return cls()
