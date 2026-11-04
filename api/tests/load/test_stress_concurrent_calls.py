"""Stress tests for concurrent AI voice call sessions."""

from __future__ import annotations

import pytest

from api.services.reliability_testing.voice_simulator import VoiceCallSessionSimulator


@pytest.mark.load
@pytest.mark.reliability
@pytest.mark.asyncio
async def test_concurrent_voice_sessions_stress():
    sim = VoiceCallSessionSimulator(
        concurrent_sessions=15,
        turns_per_session=4,
        interrupt_every_n_turns=2,
    )
    result = await sim.run()
    assert result.total == 15
    assert result.success_rate >= 0.95
    assert result.duration_s < 30.0


@pytest.mark.load
@pytest.mark.reliability
@pytest.mark.asyncio
async def test_concurrent_sessions_high_fanout():
    sim = VoiceCallSessionSimulator(concurrent_sessions=40, turns_per_session=2)
    result = await sim.run()
    assert result.succeeded >= 38
    assert result.failed <= 2
