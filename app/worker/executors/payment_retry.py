import asyncio
import random
import uuid
from typing import Any

from app.worker.executors.base import BaseExecutor


class PaymentExecutor(BaseExecutor):
    max_execution_seconds = 60

    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(random.uniform(1.0, 5.0))
        if random.random() < 0.3:
            raise RuntimeError("Payment gateway timeout: upstream returned 504")
        return {
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "status": "approved",
            "amount": payload.get("amount"),
        }
