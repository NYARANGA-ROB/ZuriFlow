"""Retry and recovery reliability tests."""

from __future__ import annotations

import pytest

from api.services.reliability_testing.failure_injector import FailureInjector, RetryRecoverySimulator


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_retry_recovery_after_injected_failures():
    sim = RetryRecoverySimulator(operations=30, max_attempts=4)
    result = await sim.run()
    assert result.total == 30
    assert result.success_rate >= 0.85


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_mpesa_daraja_retry_recovers_transient_error():
    from api.services.mpesa_daraja.retry import with_daraja_retry

    calls = {"n": 0}

    @with_daraja_retry
    async def _flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("connection timeout")
        return "ok"

    result = await _flaky()
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_whatsapp_retry_queue_reenqueue():
    from unittest.mock import AsyncMock, patch

    from api.services.whatsapp.queue import WhatsAppRetryQueue
    from api.services.whatsapp.types import OutboundPayload, WhatsAppProviderName

    payload = OutboundPayload(
        organization_id=1,
        phone_e164="+254712345678",
        body="test",
        provider=WhatsAppProviderName.META,
        attempt=1,
    )
    queue = WhatsAppRetryQueue(max_attempts=3, base_delay_s=0.01)
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock()
    with patch("api.tasks.arq.get_arq_redis", AsyncMock(return_value=mock_redis)):
        ok = await queue.enqueue_retry(payload)
    assert ok is True
    mock_redis.enqueue_job.assert_awaited_once()


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_failure_injector_wrap():
    injector = FailureInjector(fail_rate=1.0, fail_until_attempt=2)

    calls = {"n": 0}

    async def _inner():
        calls["n"] += 1
        return "done"

    wrapped = injector.wrap("k1", _inner)
    with pytest.raises(RuntimeError, match="injected failure"):
        await wrapped()
    assert await wrapped() == "done"
