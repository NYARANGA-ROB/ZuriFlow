"""STK push spike stress tests."""

from __future__ import annotations

import pytest

from api.services.reliability_testing.spike_simulators import STKPushSpikeSimulator


@pytest.mark.load
@pytest.mark.reliability
@pytest.mark.asyncio
async def test_stk_push_spike_simulated():
    sim = STKPushSpikeSimulator(spike_size=60, fail_rate=0.1)
    result = await sim.run()
    assert result.total == 60
    assert result.success_rate >= 0.85


@pytest.mark.load
@pytest.mark.reliability
@pytest.mark.asyncio
async def test_stk_push_spike_with_mock_service():
    from unittest.mock import AsyncMock

    mock = AsyncMock(return_value=type("R", (), {"success": True})())
    sim = STKPushSpikeSimulator(spike_size=25, fail_rate=0.0)
    result = await sim.run(stk_fn=mock)
    assert result.success_rate == 1.0
    assert mock.await_count == 25
