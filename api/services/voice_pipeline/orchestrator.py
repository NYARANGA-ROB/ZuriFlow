"""Async orchestration for modular voice pipelines."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from api.services.voice_pipeline.container import VoicePipelineDependencies
from api.services.voice_pipeline.metrics.interfaces import MetricName
from api.services.voice_pipeline.metrics.service import metric, now_ms, record_stage
from api.services.voice_pipeline.types import (
    LLMMessage,
    TranscriptKind,
    TTSRequest,
    VoicePipelineConfig,
)


class ModularVoiceOrchestrator:
    """Connects STT → LLM → TTS over async queues with no blocking I/O on the hot path."""

    def __init__(self, deps: VoicePipelineDependencies) -> None:
        self._deps = deps
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._conversation: list[LLMMessage] = []

    async def run(self) -> None:
        cfg = self._deps.config
        if cfg.is_realtime:
            await self._run_realtime_bridge()
            return
        await self._run_modular()

    async def _run_modular(self) -> None:
        deps = self._deps
        cfg = deps.config
        metrics = deps.metrics

        if hasattr(metrics, "start"):
            await metrics.start()

        if deps.stt is None or deps.llm is None or deps.tts is None:
            raise ValueError("Modular pipeline requires stt, llm, and tts services")

        await deps.telephony.prepare(cfg)
        transport_kwargs = deps.transport_kwargs or {}
        if deps.websocket is not None and hasattr(deps.transport, "open"):
            open_fn = deps.transport.open
            if transport_kwargs:
                await open_fn(cfg, deps.websocket, transport_kwargs=transport_kwargs)
            else:
                await open_fn(cfg, deps.websocket)

        await deps.stt.start()
        await deps.llm.start()
        await deps.tts.start()
        await deps.llm.set_system_prompt("You are a helpful voice assistant.")

        await metrics.record(
            metric(MetricName.CALL_STARTED, cfg.workflow_run_id)
        )

        self._tasks = [
            asyncio.create_task(self._pump_inbound_audio(), name="inbound-audio"),
            asyncio.create_task(self._consume_transcripts(), name="stt-consumer"),
        ]

        try:
            await self._stop.wait()
        finally:
            await self._shutdown()

    async def _pump_inbound_audio(self) -> None:
        deps = self._deps
        inbound = deps.transport.inbound()
        async for chunk in inbound.audio_chunks():
            if self._stop.is_set():
                break
            await deps.stt.push_audio(chunk)

    async def _consume_transcripts(self) -> None:
        deps = self._deps
        cfg = deps.config
        metrics = deps.metrics

        async for event in deps.stt.transcripts():
            if event.kind != TranscriptKind.FINAL:
                continue
            await metrics.record(
                metric(
                    MetricName.STT_FINAL,
                    cfg.workflow_run_id,
                    labels={"chars": str(len(event.text))},
                )
            )
            self._conversation.append(LLMMessage(role="user", content=event.text))
            await self._run_llm_turn()

    async def _run_llm_turn(self) -> None:
        deps = self._deps
        cfg = deps.config
        metrics = deps.metrics
        llm_start = now_ms()
        first_token = True
        full_text: list[str] = []

        async for stream_event in deps.llm.generate(list(self._conversation)):
            if stream_event.kind.value == "text_delta":
                if first_token:
                    await metrics.record(
                        metric(
                            MetricName.LLM_FIRST_TOKEN,
                            cfg.workflow_run_id,
                            value=now_ms() - llm_start,
                        )
                    )
                    first_token = False
                full_text.append(stream_event.text)
            elif stream_event.kind.value == "text_done":
                text = stream_event.text or "".join(full_text)
                await record_stage(
                    metrics,
                    workflow_run_id=cfg.workflow_run_id,
                    stage="llm",
                    started_ms=llm_start,
                )
                self._conversation.append(LLMMessage(role="assistant", content=text))
                await self._synthesize_and_play(text)

    async def _synthesize_and_play(self, text: str) -> None:
        deps = self._deps
        cfg = deps.config
        metrics = deps.metrics
        tts_start = now_ms()
        first_byte = True

        async for audio in deps.tts.synthesize(
            TTSRequest(text=text, sample_rate=cfg.sample_rate)
        ):
            if first_byte:
                await metrics.record(
                    metric(
                        MetricName.TTS_FIRST_BYTE,
                        cfg.workflow_run_id,
                        value=now_ms() - tts_start,
                    )
                )
                first_byte = False
            await deps.transport.outbound().send(audio)

        await metrics.record(
            metric(MetricName.TTS_DONE, cfg.workflow_run_id)
        )

    async def stop(self) -> None:
        self._stop.set()

    async def _shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        deps = self._deps
        if deps.stt:
            await deps.stt.stop()
        if deps.llm:
            await deps.llm.stop()
        if deps.tts:
            await deps.tts.stop()
        await deps.transport.close()
        await deps.telephony.close()

        if hasattr(deps.metrics, "stop"):
            await deps.metrics.stop()
        await deps.metrics.record(
            metric(MetricName.CALL_ENDED, deps.config.workflow_run_id)
        )

    async def _run_realtime_bridge(self) -> None:
        """Delegate realtime (speech-to-speech) sessions to the legacy Pipecat runner."""
        await LegacyVoiceOrchestrator(self._deps).run()


class LegacyVoiceOrchestrator:
    """Production orchestrator: delegates to ``run_pipeline_telephony`` unchanged."""

    def __init__(self, deps: VoicePipelineDependencies) -> None:
        self._deps = deps

    async def run(self) -> None:
        from api.services.pipecat.run_pipeline import run_pipeline_telephony

        deps = self._deps
        cfg = deps.config
        websocket = deps.websocket
        if websocket is None:
            raise ValueError("websocket is required for legacy orchestrator")

        await deps.telephony.prepare(cfg)
        kwargs = deps.transport_kwargs
        if kwargs is None:
            kwargs = await deps.telephony.handshake(websocket)

        logger.info(
            f"[voice_pipeline] legacy bridge run={cfg.workflow_run_id} "
            f"provider={cfg.provider_name}"
        )
        await run_pipeline_telephony(
            websocket,
            provider_name=cfg.provider_name,
            workflow_id=cfg.workflow_id,
            workflow_run_id=cfg.workflow_run_id,
            user_id=cfg.user_id,
            call_id=cfg.call_id,
            transport_kwargs=kwargs,
        )


async def run_voice_session(
    deps: VoicePipelineDependencies,
    *,
    use_legacy: bool = True,
) -> None:
    """Entry point used by WebSocket handlers."""
    if use_legacy or deps.config.is_realtime:
        await LegacyVoiceOrchestrator(deps).run()
    else:
        await ModularVoiceOrchestrator(deps).run()


def build_config_from_context(
    *,
    workflow_id: int,
    workflow_run_id: int,
    user_id: int,
    organization_id: int,
    provider_name: str,
    call_id: str,
    is_realtime: bool = False,
    telephony_configuration_id: int | None = None,
    sample_rate: int = 16000,
    extra: dict[str, Any] | None = None,
) -> VoicePipelineConfig:
    return VoicePipelineConfig(
        workflow_id=workflow_id,
        workflow_run_id=workflow_run_id,
        user_id=user_id,
        organization_id=organization_id,
        provider_name=provider_name,
        call_id=call_id,
        is_realtime=is_realtime,
        telephony_configuration_id=telephony_configuration_id,
        sample_rate=sample_rate,
        extra=extra or {},
    )
