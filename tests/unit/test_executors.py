import pytest
from unittest.mock import patch, AsyncMock

from app.worker.executors.registry import EXECUTOR_REGISTRY, get_executor


# --- registry ---

def test_registry_has_all_types():
    assert set(EXECUTOR_REGISTRY.keys()) == {"email_send", "payment_retry", "report_generate"}


def test_get_executor_returns_correct_instance():
    from app.worker.executors.email_send import EmailExecutor
    from app.worker.executors.payment_retry import PaymentExecutor
    from app.worker.executors.report_generate import ReportExecutor

    assert isinstance(get_executor("email_send"), EmailExecutor)
    assert isinstance(get_executor("payment_retry"), PaymentExecutor)
    assert isinstance(get_executor("report_generate"), ReportExecutor)


def test_get_executor_raises_for_unknown_type():
    with pytest.raises(ValueError, match="Unknown job type"):
        get_executor("nonexistent_type")


def test_executor_timeouts():
    assert get_executor("email_send").max_execution_seconds == 30
    assert get_executor("payment_retry").max_execution_seconds == 60
    assert get_executor("report_generate").max_execution_seconds == 120


# --- EmailExecutor ---

async def test_email_executor_success():
    from app.worker.executors.email_send import EmailExecutor

    with patch("app.worker.executors.email_send.random") as mock_rng, \
         patch("app.worker.executors.email_send.asyncio.sleep", new_callable=AsyncMock):
        mock_rng.uniform.return_value = 0.0
        mock_rng.random.return_value = 0.5  # > 0.1 → success

        result = await EmailExecutor().execute("job-1", {"to": "user@example.com"})

    assert result["delivered"] is True
    assert result["recipient"] == "user@example.com"
    assert result["message_id"].startswith("msg_")


async def test_email_executor_failure():
    from app.worker.executors.email_send import EmailExecutor

    with patch("app.worker.executors.email_send.random") as mock_rng, \
         patch("app.worker.executors.email_send.asyncio.sleep", new_callable=AsyncMock):
        mock_rng.uniform.return_value = 0.0
        mock_rng.random.return_value = 0.05  # < 0.1 → failure

        with pytest.raises(RuntimeError, match="SMTP"):
            await EmailExecutor().execute("job-1", {})


# --- PaymentExecutor ---

async def test_payment_executor_success():
    from app.worker.executors.payment_retry import PaymentExecutor

    with patch("app.worker.executors.payment_retry.random") as mock_rng, \
         patch("app.worker.executors.payment_retry.asyncio.sleep", new_callable=AsyncMock):
        mock_rng.uniform.return_value = 0.0
        mock_rng.random.return_value = 0.5  # > 0.3 → success

        result = await PaymentExecutor().execute("job-2", {"amount": 99.99})

    assert result["status"] == "approved"
    assert result["amount"] == 99.99
    assert result["transaction_id"].startswith("txn_")


async def test_payment_executor_failure():
    from app.worker.executors.payment_retry import PaymentExecutor

    with patch("app.worker.executors.payment_retry.random") as mock_rng, \
         patch("app.worker.executors.payment_retry.asyncio.sleep", new_callable=AsyncMock):
        mock_rng.uniform.return_value = 0.0
        mock_rng.random.return_value = 0.1  # < 0.3 → failure

        with pytest.raises(RuntimeError, match="504"):
            await PaymentExecutor().execute("job-2", {"amount": 50.0})


# --- ReportExecutor ---

async def test_report_executor_always_succeeds():
    from app.worker.executors.report_generate import ReportExecutor

    with patch("app.worker.executors.report_generate.time") as mock_time, \
         patch("app.worker.executors.report_generate.random") as mock_rng:
        mock_time.sleep.return_value = None
        mock_rng.uniform.return_value = 0.0
        mock_rng.randint.side_effect = [500, 100_000, 55555]
        mock_rng.choice.return_value = "pdf"  # not used but safe

        result = await ReportExecutor().execute("job-3", {"format": "pdf"})

    assert result["rows"] == 500
    assert result["size_bytes"] == 100_000
    assert "report_id" in result
