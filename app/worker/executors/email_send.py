import asyncio
import random
import uuid
from typing import Any

from app.worker.executors.base import BaseExecutor


class EmailExecutor(BaseExecutor):
    max_execution_seconds = 30

    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(random.uniform(0.5, 3.0))
        if random.random() < 0.1:
            raise RuntimeError("SMTP connection refused: upstream mail server unavailable")
        return {
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "delivered": True,
            "recipient": payload.get("to", "unknown"),
        }
