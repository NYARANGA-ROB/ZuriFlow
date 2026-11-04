"""Failure injection tests for workflow components."""

from __future__ import annotations

import pytest

from api.services.reliability_testing.failure_injector import FailureInjector
from api.services.reliability_testing.spike_simulators import STKPushSpikeSimulator


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_stk_spike_high_failure_rate():
    sim = STKPushSpikeSimulator(spike_size=30, fail_rate=0.8)
    result = await sim.run()
    assert result.failed > 10
    assert result.success_rate < 0.5


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_injector_failing_phase():
    injector = FailureInjector(fail_rate=0.0, fail_until_attempt=1)
    failures = 0

    async def _op():
        wrapped = injector.wrap("x", lambda: _success())
        try:
            return await wrapped()
        except RuntimeError:
            return False

    async def _success():
        return True

    async with injector.failing_phase():
        for _ in range(5):
            if not await _op():
                failures += 1
    assert failures == 5


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_full_workflow_reliability_runner():
    from api.services.reliability_testing.runner import WorkflowReliabilityRunner

    runner = WorkflowReliabilityRunner(
        concurrent_calls=8,
        stk_spike_size=15,
        whatsapp_spike_size=20,
        interruption_burst=10,
        retry_operations=15,
        skip_live_websocket=True,
    )
    report = await runner.run_all()
    assert len(report.scenarios) == 6
    assert report.overall_success_rate >= 0.7
