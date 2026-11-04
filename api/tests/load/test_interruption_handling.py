"""Interruption handling reliability under burst load."""

from __future__ import annotations

import pytest

from api.services.reliability_testing.voice_simulator import InterruptionBurstSimulator


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_interruption_burst_all_handlers_recover():
    sim = InterruptionBurstSimulator(burst_count=50, concurrent_handlers=10)
    result = await sim.run()
    assert result.total == 10
    assert result.success_rate == 1.0


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_interruption_cancellation_ordered_under_load():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
    from api.services.realtime_voice_pipeline.interruption.cancellation import (
        InterruptionCancellationManager,
    )
    from api.services.realtime_voice_pipeline.interruption.detector import (
        InterruptionEvent,
        InterruptionSource,
    )
    from api.services.realtime_voice_pipeline.interruption.recovery import (
        ConversationRecoveryManager,
    )
    from api.services.realtime_voice_pipeline.queues import PipelineQueues

    async def _burst(idx: int) -> bool:
        cfg = RealtimeVoicePipelineConfig(session_id=f"b-{idx}")
        queues = PipelineQueues(cfg)
        llm = AsyncMock()
        stt = AsyncMock()
        recovery = ConversationRecoveryManager()
        mgr = InterruptionCancellationManager(
            llm=llm, stt=stt, recovery=recovery, queues=queues, organization_id=1
        )
        mgr.mark_llm_active()
        mgr.mark_bot_speaking()
        recovery.begin_assistant_turn()
        recovery.append_assistant_delta("partial")
        for _ in range(5):
            out = await mgr.handle_interruption(
                InterruptionEvent(source=InterruptionSource.VAD, reason="burst")
            )
            if not out.get("cancelled"):
                return False
            mgr.mark_llm_active()
        await queues.close()
        return llm.interrupt.await_count >= 5

    results = await asyncio.gather(*[_burst(i) for i in range(12)])
    assert all(results)
