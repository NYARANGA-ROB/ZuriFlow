"""WhatsApp delivery spike stress tests."""

from __future__ import annotations

import pytest

from api.services.reliability_testing.spike_simulators import WhatsAppSpikeSimulator


@pytest.mark.load
@pytest.mark.reliability
@pytest.mark.asyncio
async def test_whatsapp_spike_simulated():
    sim = WhatsAppSpikeSimulator(spike_size=80, fail_rate=0.2, retry_on_failure=True)
    result = await sim.run()
    assert result.total == 80
    assert result.success_rate >= 0.75
    assert result.metadata.get("retries", 0) > 0


@pytest.mark.load
@pytest.mark.reliability
@pytest.mark.asyncio
async def test_whatsapp_spike_with_mock_sender():
    from unittest.mock import AsyncMock

    calls = {"n": 0}

    async def _send(payload):
        calls["n"] += 1
        if payload.get("attempt", 1) == 1:
            return {"success": False, "error": "503"}
        return {"success": True}

    sim = WhatsAppSpikeSimulator(spike_size=20, retry_on_failure=True)
    result = await sim.run(send_fn=_send)
    assert result.success_rate >= 0.9
    assert calls["n"] >= 20
