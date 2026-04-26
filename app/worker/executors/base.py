from abc import ABC, abstractmethod
from typing import Any


class BaseExecutor(ABC):
    max_execution_seconds: int = 300

    @abstractmethod
    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
