"""Dependency injection container for voice pipeline services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from api.services.voice_pipeline.llm.interfaces import LLMService, RealtimeLLMService
from api.services.voice_pipeline.metrics.interfaces import MetricsCollector
from api.services.voice_pipeline.speech_to_text.interfaces import SpeechToTextService
from api.services.voice_pipeline.streaming.interfaces import MediaTransport
from api.services.voice_pipeline.telephony.interfaces import TelephonySession
from api.services.voice_pipeline.text_to_speech.interfaces import TextToSpeechService
from api.services.voice_pipeline.types import VoicePipelineConfig


@dataclass
class VoicePipelineDependencies:
    """Injectable service graph for one voice session."""

    config: VoicePipelineConfig
    telephony: TelephonySession
    transport: MediaTransport
    stt: SpeechToTextService | None
    llm: LLMService | None
    tts: TextToSpeechService | None
    realtime_llm: RealtimeLLMService | None
    metrics: MetricsCollector
    websocket: Any = None
    transport_kwargs: dict[str, Any] | None = None


VoicePipelineFactory = Callable[[VoicePipelineConfig], VoicePipelineDependencies]


@dataclass
class VoicePipelineContainer:
    """Builds ``VoicePipelineDependencies`` from factories (DI root)."""

    telephony_factory: Callable[[str], TelephonySession]
    transport_factory: Callable[[], MediaTransport]
    stt_factory: Callable[[VoicePipelineConfig], SpeechToTextService | None]
    llm_factory: Callable[[VoicePipelineConfig], LLMService | None]
    tts_factory: Callable[[VoicePipelineConfig], TextToSpeechService | None]
    realtime_llm_factory: Callable[[VoicePipelineConfig], RealtimeLLMService | None]
    metrics_factory: Callable[[int], MetricsCollector]

    def build(
        self,
        config: VoicePipelineConfig,
        *,
        websocket: Any = None,
        transport_kwargs: dict[str, Any] | None = None,
    ) -> VoicePipelineDependencies:
        return VoicePipelineDependencies(
            config=config,
            telephony=self.telephony_factory(config.provider_name),
            transport=self.transport_factory(),
            stt=self.stt_factory(config),
            llm=self.llm_factory(config),
            tts=self.tts_factory(config),
            realtime_llm=self.realtime_llm_factory(config),
            metrics=self.metrics_factory(config.workflow_run_id),
            websocket=websocket,
            transport_kwargs=transport_kwargs,
        )


def production_pipecat_container() -> VoicePipelineContainer:
    """Container wired to Pipecat service factories (bridge mode)."""
    from api.db import db_client
    from api.services.configuration.ai_model_configuration import (
        get_effective_ai_model_configuration_for_workflow,
    )
    from api.services.managed_model_services import ensure_mps_correlation_id
    from api.services.pipecat.audio_config import create_audio_config
    from api.services.voice_pipeline.llm.service import (
        PipecatLLMAdapter,
        PipecatRealtimeLLMAdapter,
    )
    from api.services.voice_pipeline.metrics.service import AsyncMetricsCollector
    from api.services.voice_pipeline.speech_to_text.service import PipecatSTTAdapter
    from api.services.voice_pipeline.streaming.service import PipecatMediaTransport
    from api.services.voice_pipeline.telephony.service import RegistryTelephonySession
    from api.services.voice_pipeline.text_to_speech.service import PipecatTTSAdapter

    async def _resolve_user_config(cfg: VoicePipelineConfig):
        workflow_run = await db_client.get_workflow_run(
            cfg.workflow_run_id, cfg.user_id
        )
        workflow = await db_client.get_workflow(cfg.workflow_id, cfg.user_id)
        run_configs = (
            (workflow_run.definition.workflow_configurations or {})
            if workflow_run
            else {}
        )
        return await get_effective_ai_model_configuration_for_workflow(
            user_id=cfg.user_id,
            organization_id=cfg.organization_id,
            workflow_configurations=run_configs,
        )

    def stt_factory(cfg: VoicePipelineConfig) -> SpeechToTextService | None:
        if cfg.is_realtime:
            return None

        async def _build() -> PipecatSTTAdapter:
            user_config = await _resolve_user_config(cfg)
            audio_config = create_audio_config(cfg.provider_name)
            correlation_id = await ensure_mps_correlation_id(
                ai_model_config=user_config,
                workflow_run_id=cfg.workflow_run_id,
                initial_context=cfg.extra,
            )
            return PipecatSTTAdapter(
                user_config=user_config,
                audio_config=audio_config,
                correlation_id=correlation_id,
            )

        # Factory returns sync placeholder; orchestrator calls start() which
        # must be extended to await async build — use lazy adapter instead.
        class _LazySTT:
            def __init__(self):
                self._inner: PipecatSTTAdapter | None = None

            async def _ensure(self):
                if self._inner is None:
                    self._inner = await _build()
                return self._inner

            async def start(self):
                return await (await self._ensure()).start()

            async def stop(self):
                if self._inner:
                    await self._inner.stop()

            async def push_audio(self, chunk):
                await (await self._ensure()).push_audio(chunk)

            async def transcripts(self):
                inner = await self._ensure()
                async for t in inner.transcripts():
                    yield t

        return _LazySTT()  # type: ignore[return-value]

    def llm_factory(cfg: VoicePipelineConfig) -> LLMService | None:
        if cfg.is_realtime:
            return None

        class _LazyLLM:
            def __init__(self):
                self._inner: PipecatLLMAdapter | None = None

            async def _ensure(self):
                if self._inner is None:
                    user_config = await _resolve_user_config(cfg)
                    correlation_id = await ensure_mps_correlation_id(
                        ai_model_config=user_config,
                        workflow_run_id=cfg.workflow_run_id,
                        initial_context=cfg.extra,
                    )
                    self._inner = PipecatLLMAdapter(
                        user_config=user_config, correlation_id=correlation_id
                    )
                return self._inner

            async def start(self):
                return await (await self._ensure()).start()

            async def stop(self):
                if self._inner:
                    await self._inner.stop()

            async def set_system_prompt(self, prompt: str):
                await (await self._ensure()).set_system_prompt(prompt)

            async def generate(self, messages, *, tools=None):
                inner = await self._ensure()
                async for ev in inner.generate(messages, tools=tools):
                    yield ev

        return _LazyLLM()  # type: ignore[return-value]

    def tts_factory(cfg: VoicePipelineConfig) -> TextToSpeechService | None:
        if cfg.is_realtime:
            return None

        class _LazyTTS:
            def __init__(self):
                self._inner: PipecatTTSAdapter | None = None

            async def _ensure(self):
                if self._inner is None:
                    user_config = await _resolve_user_config(cfg)
                    audio_config = create_audio_config(cfg.provider_name)
                    correlation_id = await ensure_mps_correlation_id(
                        ai_model_config=user_config,
                        workflow_run_id=cfg.workflow_run_id,
                        initial_context=cfg.extra,
                    )
                    self._inner = PipecatTTSAdapter(
                        user_config=user_config,
                        audio_config=audio_config,
                        correlation_id=correlation_id,
                    )
                return self._inner

            async def start(self):
                return await (await self._ensure()).start()

            async def stop(self):
                if self._inner:
                    await self._inner.stop()

            async def synthesize(self, request):
                inner = await self._ensure()
                async for chunk in inner.synthesize(request):
                    yield chunk

        return _LazyTTS()  # type: ignore[return-value]

    def realtime_factory(cfg: VoicePipelineConfig) -> RealtimeLLMService | None:
        if not cfg.is_realtime:
            return None

        class _LazyRealtime:
            def __init__(self):
                self._inner: PipecatRealtimeLLMAdapter | None = None

            async def _ensure(self):
                if self._inner is None:
                    user_config = await _resolve_user_config(cfg)
                    audio_config = create_audio_config(cfg.provider_name)
                    self._inner = PipecatRealtimeLLMAdapter(
                        user_config=user_config, audio_config=audio_config
                    )
                return self._inner

            async def start(self):
                return await (await self._ensure()).start()

            async def stop(self):
                if self._inner:
                    await self._inner.stop()

            async def set_system_prompt(self, prompt: str):
                await (await self._ensure()).set_system_prompt(prompt)

        return _LazyRealtime()  # type: ignore[return-value]

    return VoicePipelineContainer(
        telephony_factory=lambda provider: RegistryTelephonySession(
            provider_name=provider
        ),
        transport_factory=PipecatMediaTransport,
        stt_factory=stt_factory,
        llm_factory=llm_factory,
        tts_factory=tts_factory,
        realtime_llm_factory=realtime_factory,
        metrics_factory=lambda run_id: AsyncMetricsCollector(run_id),
    )


def default_example_container() -> VoicePipelineContainer:
    """Container wired with in-memory example services (echo bot)."""
    from api.services.voice_pipeline.llm.service import EchoLLMService
    from api.services.voice_pipeline.metrics.service import AsyncMetricsCollector
    from api.services.voice_pipeline.speech_to_text.service import EchoSTTService
    from api.services.voice_pipeline.streaming.service import InMemoryMediaTransport
    from api.services.voice_pipeline.telephony.service import RegistryTelephonySession
    from api.services.voice_pipeline.text_to_speech.service import ToneTTSService

    return VoicePipelineContainer(
        telephony_factory=lambda _provider: RegistryTelephonySession(
            provider_name=_provider
        ),
        transport_factory=InMemoryMediaTransport,
        stt_factory=lambda _cfg: EchoSTTService(),
        llm_factory=lambda _cfg: EchoLLMService(),
        tts_factory=lambda cfg: ToneTTSService(sample_rate=cfg.sample_rate),
        realtime_llm_factory=lambda _cfg: None,
        metrics_factory=lambda run_id: AsyncMetricsCollector(run_id),
    )
