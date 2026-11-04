"""Top-level orchestration service for the realtime voice pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from api.services.realtime_audio.connection_manager import AudioSession
from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.manager import (
    RealtimeVoicePipelineDependencies,
    RealtimeVoicePipelineManager,
)
from api.services.realtime_voice_pipeline.transport import RealtimeAudioMediaTransport


class RealtimeVoiceOrchestrator:
    """Connects inbound WebSocket audio → STT → LLM → TTS → outbound playback."""

    def __init__(self, deps: RealtimeVoicePipelineDependencies) -> None:
        self._deps = deps
        self._manager = RealtimeVoicePipelineManager(deps)

    @property
    def manager(self) -> RealtimeVoicePipelineManager:
        return self._manager

    async def run(self) -> None:
        from api.services.realtime_observability.correlation import (
            bind_call_correlation,
            correlation_from_session,
        )
        from api.services.realtime_observability.metrics import CALL_STARTUP_MS
        from api.services.realtime_observability.percentiles import record_stage_ms
        from api.services.realtime_observability.tracing import trace_session
        import time as _time

        cfg = self._deps.config
        corr = correlation_from_session(
            session_id=cfg.session_id,
            organization_id=cfg.organization_id,
            workflow_run_id=self._deps.workflow_run_id,
        )
        started = _time.perf_counter()
        with trace_session(cfg.session_id, trace_id=corr.trace_id), bind_call_correlation(corr):
            await self._manager.start()
            startup_ms = (_time.perf_counter() - started) * 1000.0
            CALL_STARTUP_MS.observe(startup_ms)
            record_stage_ms("call_startup", startup_ms)
            try:
                await self._manager.wait()
            except asyncio.CancelledError:
                await self._manager.shutdown()
                raise

    async def stop(self) -> None:
        await self._manager.stop()

    async def interrupt(self, *, reason: str = "barge_in") -> None:
        await self._manager.interrupt(reason=reason)


async def run_realtime_voice_pipeline(
    session: AudioSession,
    *,
    stt: Any,
    llm: Any,
    tts: Any,
    metrics: Any,
    system_prompt: str = "You are a helpful voice assistant.",
    workflow_run_id: int = 0,
) -> RealtimeVoiceOrchestrator:
    """Build and start the pipeline for an established ``AudioSession``."""
    config = RealtimeVoicePipelineConfig(
        session_id=session.session_id,
        sample_rate=session.sample_rate,
        channels=session.channels,
        system_prompt=system_prompt,
    )
    transport = RealtimeAudioMediaTransport(session)
    deps = RealtimeVoicePipelineDependencies(
        config=config,
        transport=transport,
        stt=stt,
        llm=llm,
        tts=tts,
        metrics=metrics,
        workflow_run_id=workflow_run_id,
    )
    orchestrator = RealtimeVoiceOrchestrator(deps)
    asyncio.create_task(orchestrator.run(), name=f"voice-pipeline-{session.session_id[:8]}")
    logger.info("realtime voice orchestrator attached session_id={}", session.session_id)
    return orchestrator
