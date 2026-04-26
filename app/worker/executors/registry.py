from app.worker.executors.base import BaseExecutor

EXECUTOR_REGISTRY: dict[str, type[BaseExecutor]] = {}


def get_executor(job_type: str) -> BaseExecutor:
    cls = EXECUTOR_REGISTRY.get(job_type)
    if cls is None:
        raise ValueError(
            f"Unknown job type: {job_type!r}. Valid types: {list(EXECUTOR_REGISTRY.keys())}"
        )
    return cls()
