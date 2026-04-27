import asyncio
import random
import time
from typing import Any

from app.worker.executors.base import BaseExecutor


def _generate_report_sync(payload: dict[str, Any]) -> dict[str, Any]:
    time.sleep(random.uniform(1.0, 5.0))
    return {
        "rows": random.randint(100, 10_000),
        "format": payload.get("format", "pdf"),
        "size_bytes": random.randint(50_000, 500_000),
        "report_id": f"rpt_{random.randint(10000, 99999)}",
    }


class ReportExecutor(BaseExecutor):
    max_execution_seconds = 120

    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _generate_report_sync, payload)
