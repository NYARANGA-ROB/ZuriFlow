"""Lifecycle manager for realtime voice pipeline tasks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from loguru import logger

from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.handlers import (
    ControlEventHandler,
    InboundAudioHandler,
    InterruptionHandler,
    LLMResponseHandler,
    LowLatencyInboundHandler,
    STTAudioHandler,
    STTRelayHandler,
    TranscriptEventHandler,
    build_vad,
)
from api.services.realtime_voice_pipeline.interruption.cancellation import (
    InterruptionCancellationManager,
)
from api.services.realtime_voice_pipeline.interruption.detector import InterruptionDetector
from api.services.realtime_voice_pipeline.interruption.recovery import (
    ConversationRecoveryManager,
)
from api.services.realtime_voice_pipeline.interruption.tts_stop import TTSStopHandler
from api.services.realtime_voice_pipeline.latency import PipelineLatencyTracker
from api.services.realtime_voice_pipeline.queues import PipelineQueues
from api.services.realtime_voice_pipeline.transport import RealtimeAudioMediaTransport
from api.services.realtime_voice_pipeline.types import PipelineControlEvent, PipelineControlKind
from api.services.kenyan_conversation.integration import get_kenyan_conversation_behavior
from api.services.realtime_conversation_memory.integration import get_call_memory
from api.services.voice_mpesa.engine import get_voice_mpesa_engine
from api.services.voice_mpesa.integration import bootstrap_voice_mpesa_session
from api.services.voice_pipeline.llm.streaming_adapter import StreamingLLMBridge
from api.services.voice_pipeline.metrics.interfaces import MetricsCollector, MetricName
from api.services.voice_pipeline.metrics.service import metric
from api.services.voice_pipeline.speech_to_text.streaming_adapter import StreamingSTTBridge
from api.services.voice_pipeline.text_to_speech.streaming_adapter import StreamingTTSBridge
from api.services.voice_pipeline.types import VoicePipelineConfig


@dataclass
class RealtimeVoicePipelineDependencies:
    """Injectable services for one realtime voice session."""

    config: RealtimeVoicePipelineConfig
    transport: RealtimeAudioMediaTransport
    stt: StreamingSTTBridge
    llm: StreamingLLMBridge
    tts: StreamingTTSBridge
    metrics: MetricsCollector
    workflow_run_id: int = 0


@dataclass
class RealtimeVoicePipelineManager:
    """Starts, supervises, and tears down all pipeline asyncio tasks."""

    deps: RealtimeVoicePipelineDependencies
    queues: PipelineQueues = field(init=False)
    cancellation: InterruptionCancellationManager = field(init=False)
    recovery: ConversationRecoveryManager = field(init=False)
    detector: InterruptionDetector = field(init=False)
    latency: PipelineLatencyTracker = field(init=False)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _tasks: list[asyncio.Task] = field(default_factory=list)
    _shutdown_done: bool = field(default=False, init=False)
    _transcript_handler: TranscriptEventHandler | None = field(default=None, init=False)
    _memory: object | None = field(default=None, init=False)
    _memory_session_id: str | None = field(default=None, init=False)
    _voice_mpesa: object | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.queues = PipelineQueues(self.deps.config)
        self.recovery = ConversationRecoveryManager()
        self.latency = PipelineLatencyTracker(
            workflow_run_id=self.deps.workflow_run_id,
            metrics=self.deps.metrics,
            session_id=self.deps.config.session_id,
            organization_id=self.deps.config.organization_id,
        )
        if hasattr(self.deps.metrics, "bind_session"):
            self.deps.metrics.bind_session(self.deps.config.session_id)
        self.cancellation = InterruptionCancellationManager(
            llm=self.deps.llm,
            stt=self.deps.stt,
            recovery=self.recovery,
            queues=self.queues,
        )
        self.cancellation.tts_stop = TTSStopHandler(
            tts=self.deps.tts,
            queues=self.queues,
        )
        self.detector = InterruptionDetector(
            config=self.deps.config,
            is_bot_active=lambda: self.cancellation.should_barge_in,
        )

    async def start(self) -> None:
        deps = self.deps
        cfg = deps.config

        if hasattr(deps.metrics, "start"):
            await deps.metrics.start()

        await deps.transport.open(
            VoicePipelineConfig(
                workflow_id=0,
                workflow_run_id=deps.workflow_run_id,
                user_id=0,
                organization_id=0,
                provider_name="realtime_audio",
                call_id=cfg.session_id,
                sample_rate=cfg.sample_rate,
            ),
        )

        if cfg.direct_outbound:
            outbound = deps.transport.outbound()

            async def _direct_send(chunk):
                await outbound.send(chunk)

            deps.transport.bind_direct_outbound(_direct_send)
        else:
            deps.transport.bind_outbound_queue(self.queues.outbound_audio)

        if cfg.parallel_service_start:
            await asyncio.gather(
                deps.stt.start(),
                deps.llm.start(),
                deps.tts.start(),
            )
        else:
            await deps.stt.start()
            await deps.llm.start()
            await deps.tts.start()

        behavior = None
        if cfg.kenyan_conversation_enabled:
            behavior = get_kenyan_conversation_behavior(domain=cfg.kenyan_domain)

        memory = None
        session_id = cfg.session_id
        if cfg.realtime_memory_enabled:
            memory = get_call_memory(session_id)
        self._memory = memory
        self._memory_session_id = session_id

        self.cancellation.session_id = session_id
        self.cancellation.organization_id = cfg.organization_id
        self.cancellation.workflow_run_id = deps.workflow_run_id

        voice_mpesa = None
        if cfg.voice_mpesa_enabled and cfg.organization_id > 0 and cfg.phone_e164:
            voice_mpesa = get_voice_mpesa_engine()
            self._voice_mpesa = voice_mpesa
            await bootstrap_voice_mpesa_session(
                voice_mpesa,
                session_id=session_id,
                organization_id=cfg.organization_id,
                workflow_run_id=deps.workflow_run_id,
                phone_e164=cfg.phone_e164,
                customer_name=cfg.customer_name,
                amount=cfg.payment_amount,
                language=cfg.payment_language,
            )

        system_prompt = cfg.system_prompt
        if behavior is not None:
            system_prompt = behavior.system_prompt(custom_instructions=cfg.system_prompt)

        await deps.llm.set_system_prompt(system_prompt)

        await deps.metrics.record(
            metric(MetricName.CALL_STARTED, deps.workflow_run_id)
        )

        vad = build_vad(cfg)
        self._transcript_handler = TranscriptEventHandler(
            queues=self.queues,
            detector=self.detector,
            cancellation=self.cancellation,
            recovery=self.recovery,
            latency=self.latency,
            config=cfg,
            stop=self._stop,
            behavior=behavior,
            memory=memory,
            voice_mpesa=voice_mpesa,
            kenyan_intent_enabled=cfg.kenyan_intent_enabled,
            call_routing_enabled=cfg.call_routing_enabled,
            organization_id=cfg.organization_id,
            workflow_run_id=deps.workflow_run_id,
            phone_e164=cfg.phone_e164,
            customer_name=cfg.customer_name,
            session_id=cfg.session_id,
        )

        inbound = deps.transport.inbound()
        tasks: list[tuple[str, object]] = []

        if cfg.low_latency_mode:
            tasks.append(
                (
                    "pipeline-inbound",
                    LowLatencyInboundHandler(
                        stt=deps.stt,
                        transport=deps.transport,
                        queues=self.queues,
                        vad=vad,
                        detector=self.detector,
                        cancellation=self.cancellation,
                        config=cfg,
                        stop=self._stop,
                    ).run(inbound),
                )
            )
        else:
            tasks.extend(
                [
                    (
                        "pipeline-inbound",
                        InboundAudioHandler(queues=self.queues, stop=self._stop).run(
                            inbound
                        ),
                    ),
                    (
                        "pipeline-stt-audio",
                        STTAudioHandler(
                            stt=deps.stt, queues=self.queues, vad=vad, stop=self._stop
                        ).run(),
                    ),
                ]
            )

        tasks.extend(
            [
                (
                    "pipeline-stt-relay",
                    STTRelayHandler(
                        stt=deps.stt, queues=self.queues, stop=self._stop
                    ).run(),
                ),
            ]
        )

        if not cfg.inline_vad:
            tasks.append(
                (
                    "pipeline-interruption",
                    InterruptionHandler(
                        queues=self.queues,
                        detector=self.detector,
                        cancellation=self.cancellation,
                        stop=self._stop,
                    ).run(),
                )
            )

        tasks.extend(
            [
                (
                    "pipeline-transcripts",
                    self._transcript_handler.run(),
                ),
                (
                    "pipeline-llm",
                    LLMResponseHandler(
                        llm=deps.llm,
                        tts=deps.tts,
                        transport=deps.transport,
                        queues=self.queues,
                        cancellation=self.cancellation,
                        recovery=self.recovery,
                        latency=self.latency,
                        config=cfg,
                        transcript_handler=self._transcript_handler,
                        stop=self._stop,
                        behavior=behavior,
                        memory=memory,
                        voice_mpesa=voice_mpesa,
                        kenyan_intent_enabled=cfg.kenyan_intent_enabled,
                        call_routing_enabled=cfg.call_routing_enabled,
                        session_id=cfg.session_id,
                    ).run(),
                ),
                (
                    "pipeline-control",
                    ControlEventHandler(
                        queues=self.queues,
                        cancellation=self.cancellation,
                        detector=self.detector,
                        stop=self._stop,
                    ).run(),
                ),
            ]
        )

        self._tasks = [
            asyncio.create_task(coro, name=name) for name, coro in tasks
        ]
        logger.info(
            "realtime voice pipeline started session_id={} low_latency={}",
            cfg.session_id,
            cfg.low_latency_mode,
        )

    async def interrupt(self, *, reason: str = "external") -> None:
        await self.queues.put_control(
            PipelineControlEvent(kind=PipelineControlKind.INTERRUPT, reason=reason)
        )

    async def stop(self, *, reason: str = "shutdown") -> None:
        self._stop.set()
        self.queues.signal_stop()
        await self.queues.put_control(
            PipelineControlEvent(kind=PipelineControlKind.SHUTDOWN, reason=reason)
        )

    async def wait(self) -> None:
        if not self._tasks:
            return
        while self._tasks and not self._stop.is_set():
            done, _pending = await asyncio.wait(
                self._tasks, return_when=asyncio.FIRST_COMPLETED
            )
            fatal = False
            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None:
                    logger.error(
                        "pipeline task {} failed session_id={}: {}",
                        task.get_name(),
                        self.deps.config.session_id[:8],
                        exc,
                    )
                    fatal = True
                elif not self._stop.is_set():
                    logger.warning(
                        "pipeline task {} exited early session_id={}",
                        task.get_name(),
                        self.deps.config.session_id[:8],
                    )
                    fatal = True
            if fatal:
                self._stop.set()
                break
        await self.shutdown()

    async def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._stop.set()
        self.queues.signal_stop()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        await self.queues.close()
        deps = self.deps
        await deps.stt.stop()
        await deps.llm.stop()
        await deps.tts.stop()
        await deps.transport.close()

        if hasattr(deps.metrics, "stop"):
            await deps.metrics.stop()
        await deps.metrics.record(
            metric(MetricName.CALL_ENDED, deps.workflow_run_id)
        )

        if self._memory is not None and deps.workflow_run_id and self._memory_session_id:
            await self._persist_conversation_memory(
                workflow_run_id=deps.workflow_run_id,
            )

        if self._voice_mpesa is not None and self._memory_session_id:
            await self._voice_mpesa.shutdown_session(self._memory_session_id)

        from api.constants import VOICE_COST_OPTIMIZATION_ENABLED

        if VOICE_COST_OPTIMIZATION_ENABLED and self._memory_session_id:
            from api.services.voice_cost_optimization.service import (
                get_voice_cost_optimization_service,
            )

            await get_voice_cost_optimization_service().tracker().persist_session(
                self._memory_session_id
            )

        if deps.config.kenyan_intent_enabled and self._memory_session_id:
            from api.services.kenyan_intent.service import get_realtime_intent_service

            get_realtime_intent_service().end_session(self._memory_session_id)

        if deps.config.call_routing_enabled and self._memory_session_id:
            from api.services.call_routing.orchestrator import get_call_routing_orchestrator

            await get_call_routing_orchestrator().end_session(self._memory_session_id)

        logger.info(
            "realtime voice pipeline stopped session_id={} outbound_dropped={}",
            deps.config.session_id,
            self.queues.outbound_dropped,
        )

    async def _persist_conversation_memory(self, *, workflow_run_id: int) -> None:
        memory = self._memory
        session_id = self._memory_session_id
        if memory is None or not session_id:
            return
        try:
            snap = memory.end_session(session_id)
            if snap is None:
                return
            from api.db import db_client

            await db_client.update_workflow_run(
                run_id=workflow_run_id,
                gathered_context={
                    "conversation_memory": snap.to_dict(),
                    "memory_session_id": session_id,
                },
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist conversation memory for run {}: {}",
                workflow_run_id,
                exc,
            )
