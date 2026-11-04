"""Event-driven stage handlers for the realtime voice pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.interruption.cancellation import (
    InterruptionCancellationManager,
)
from api.services.realtime_voice_pipeline.interruption.detector import InterruptionDetector
from api.services.realtime_voice_pipeline.interruption.recovery import (
    ConversationRecoveryManager,
)
from api.services.realtime_voice_pipeline.interruption.vad import (
    VADConfig,
    VoiceActivityDetector,
)
from api.services.realtime_voice_pipeline.latency import PipelineLatencyTracker
from api.services.realtime_voice_pipeline.queues import PipelineQueues
from api.services.realtime_voice_pipeline.transport import RealtimeAudioMediaTransport
from api.services.realtime_voice_pipeline.types import PipelineControlKind
from api.services.voice_pipeline.llm.streaming_adapter import StreamingLLMBridge
from api.services.voice_pipeline.speech_to_text.streaming_adapter import StreamingSTTBridge
from api.services.voice_pipeline.text_to_speech.streaming_adapter import StreamingTTSBridge
from api.services.voice_pipeline.types import AudioChunk, LLMMessage, LLMStreamKind, TranscriptKind

if TYPE_CHECKING:
    from api.services.call_routing.types import CallRoutingResult
    from api.services.kenyan_conversation.behavior import KenyanConversationBehavior
    from api.services.kenyan_intent.types import RouteDecision
    from api.services.realtime_conversation_memory.service import (
        RealtimeConversationMemoryService,
    )
    from api.services.voice_mpesa.engine import VoiceMpesaWorkflowEngine


@dataclass
class LowLatencyInboundHandler:
    """Single-hop inbound: transport → VAD + STT (no intermediate audio queue)."""

    stt: StreamingSTTBridge
    transport: RealtimeAudioMediaTransport
    queues: PipelineQueues
    vad: VoiceActivityDetector
    detector: InterruptionDetector
    cancellation: InterruptionCancellationManager
    config: RealtimeVoicePipelineConfig
    stop: asyncio.Event

    async def run(self, inbound) -> None:
        inline_vad = self.config.inline_vad
        interrupt_queue: asyncio.Queue = asyncio.Queue(maxsize=8)

        async def _interrupt_worker() -> None:
            while not self.stop.is_set():
                try:
                    interruption = await asyncio.wait_for(
                        interrupt_queue.get(), timeout=0.25
                    )
                except asyncio.TimeoutError:
                    continue
                if interruption is None:
                    break
                await self.cancellation.handle_interruption(interruption)
                self.detector.mark_handled()

        worker = asyncio.create_task(_interrupt_worker(), name="vad-interrupt-worker")
        try:
            async for chunk in inbound.audio_chunks():
                if self.stop.is_set():
                    break
                await self.stt.push_audio(chunk)
                self._process_vad(chunk, inline_vad=inline_vad, interrupt_queue=interrupt_queue)
        finally:
            try:
                interrupt_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    def _process_vad(
        self,
        chunk: AudioChunk,
        *,
        inline_vad: bool,
        interrupt_queue: asyncio.Queue,
    ) -> None:
        for vad_event in self.vad.process(
            chunk.pcm,
            sample_rate=chunk.sample_rate,
            timestamp_ms=chunk.timestamp_ms,
        ):
            if inline_vad:
                interruption = self.detector.on_vad(vad_event)
                if interruption:
                    try:
                        interrupt_queue.put_nowait(interruption)
                    except asyncio.QueueFull:
                        try:
                            interrupt_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            interrupt_queue.put_nowait(interruption)
                        except asyncio.QueueFull:
                            pass
            else:
                self.queues.put_vad(vad_event)


@dataclass
class InboundAudioHandler:
    """Pump inbound transport audio into the pipeline queue (legacy path)."""

    queues: PipelineQueues
    stop: asyncio.Event

    async def run(self, inbound) -> None:
        async for chunk in inbound.audio_chunks():
            if self.stop.is_set():
                break
            if not self.queues.put_inbound(chunk):
                logger.debug("inbound audio dropped (backpressure)")


@dataclass
class STTAudioHandler:
    """Drain inbound audio queue, run VAD, and feed STT (legacy path)."""

    stt: StreamingSTTBridge
    queues: PipelineQueues
    vad: VoiceActivityDetector
    stop: asyncio.Event

    async def run(self) -> None:
        async for chunk in self.queues.iter_inbound():
            if self.stop.is_set():
                break
            for vad_event in self.vad.process(
                chunk.pcm,
                sample_rate=chunk.sample_rate,
                timestamp_ms=chunk.timestamp_ms,
            ):
                self.queues.put_vad(vad_event)
            await self.stt.push_audio(chunk)


@dataclass
class STTRelayHandler:
    """Relay STT transcript events into the pipeline transcript queue."""

    stt: StreamingSTTBridge
    queues: PipelineQueues
    stop: asyncio.Event

    async def run(self) -> None:
        async for event in self.stt.transcripts():
            if self.stop.is_set():
                break
            if not self.queues.put_transcript(event):
                logger.debug("transcript event dropped (backpressure)")


@dataclass
class InterruptionHandler:
    """Consume VAD events queue (legacy path when inline_vad=False)."""

    queues: PipelineQueues
    detector: InterruptionDetector
    cancellation: InterruptionCancellationManager
    stop: asyncio.Event

    async def run(self) -> None:
        async for event in self.queues.iter_vad_events():
            if self.stop.is_set():
                break
            interruption = self.detector.on_vad(event)
            if interruption:
                await self.cancellation.handle_interruption(interruption)
                self.detector.mark_handled()


class TranscriptEventHandler:
    """Detect STT-based interruptions and trigger LLM turns on finals."""

    def __init__(
        self,
        *,
        queues: PipelineQueues,
        detector: InterruptionDetector,
        cancellation: InterruptionCancellationManager,
        recovery: ConversationRecoveryManager,
        latency: PipelineLatencyTracker,
        config: RealtimeVoicePipelineConfig,
        stop: asyncio.Event,
        behavior: KenyanConversationBehavior | None = None,
        memory: RealtimeConversationMemoryService | None = None,
        voice_mpesa: VoiceMpesaWorkflowEngine | None = None,
        kenyan_intent_enabled: bool = False,
        call_routing_enabled: bool = False,
        organization_id: int = 0,
        workflow_run_id: int = 0,
        phone_e164: str = "",
        customer_name: str = "there",
        session_id: str = "",
    ) -> None:
        self.queues = queues
        self.detector = detector
        self.cancellation = cancellation
        self.recovery = recovery
        self.latency = latency
        self.config = config
        self.stop = stop
        self.behavior = behavior
        self.memory = memory
        self.voice_mpesa = voice_mpesa
        self.kenyan_intent_enabled = kenyan_intent_enabled
        self.call_routing_enabled = call_routing_enabled
        self.organization_id = organization_id
        self.workflow_run_id = workflow_run_id
        self.phone_e164 = phone_e164
        self.customer_name = customer_name
        self.session_id = session_id
        self._turn_lock = asyncio.Lock()
        self._pending_turn = asyncio.Event()
        self._last_route: RouteDecision | None = None
        self._last_routing: CallRoutingResult | None = None

    async def run(self) -> None:
        async for event in self.queues.iter_transcripts():
            if self.stop.is_set():
                break

            interruption = self.detector.on_transcript(event)
            if interruption:
                await self.cancellation.handle_interruption(interruption)
                self.detector.mark_handled()
                if self.kenyan_intent_enabled and self.session_id:
                    from api.services.kenyan_intent.service import get_realtime_intent_service

                    partial = event.text.strip() if event.kind != TranscriptKind.FINAL else ""
                    get_realtime_intent_service().on_interrupt(
                        self.session_id, partial_text=partial
                    )

            if event.kind == TranscriptKind.PARTIAL:
                if self.kenyan_intent_enabled and event.text.strip() and self.session_id:
                    await self._infer_caller_intent(event.text, is_final=False)
                continue

            if not event.text.strip():
                continue

            async with self._turn_lock:
                if self.cancellation.should_barge_in:
                    await self.cancellation.interrupt_all(reason="final_before_turn")
                self.latency.begin_turn(trigger="stt_final")
                self.latency.mark("stt_final")
                user_text = event.text.strip()
                if self.behavior is not None:
                    import time as _time

                    t0 = _time.perf_counter()
                    user_text = self.behavior.normalize_caller_text(user_text)
                    self.latency.mark_duration("normalize", (_time.perf_counter() - t0) * 1000.0)
                self.recovery.append_user(user_text)
                if self.memory is not None and self.session_id:
                    self.memory.session(self.session_id).on_user_turn(user_text)
                if self.kenyan_intent_enabled and self.session_id:
                    import time as _time

                    t1 = _time.perf_counter()
                    await self._infer_caller_intent(user_text, is_final=True)
                    self.latency.mark_duration("intent", (_time.perf_counter() - t1) * 1000.0)
                if self.call_routing_enabled and self.organization_id > 0:
                    from api.services.kenya_production.async_tasks import fire_and_forget

                    fire_and_forget(self._handle_call_routing(), name="call-routing")
                if self.organization_id > 0 and user_text:
                    from api.services.kenya_production.async_tasks import fire_and_forget

                    async def _sentiment() -> None:
                        from api.services.voice_analytics.integration import (
                            track_customer_sentiment,
                        )

                        track_customer_sentiment(
                            organization_id=self.organization_id,
                            text=user_text,
                            session_id=self.session_id,
                            workflow_run_id=self.workflow_run_id,
                        )

                    fire_and_forget(_sentiment(), name="sentiment")
                if self.voice_mpesa is not None and self.organization_id > 0:
                    await self._handle_voice_mpesa_turn(user_text)
                self._pending_turn.set()

    @property
    def conversation(self) -> list[LLMMessage]:
        return self.recovery.messages_for_generation()

    async def wait_for_turn(self) -> None:
        await self._pending_turn.wait()
        self._pending_turn.clear()

    async def _infer_caller_intent(self, text: str, *, is_final: bool) -> None:
        from api.services.kenya_production.bottleneck_audit import StageTimer
        from api.services.kenyan_intent.integration import infer_caller_intent
        from api.services.kenyan_intent.service import get_realtime_intent_service

        with StageTimer("intent_inference"):
            if is_final:
                from api.services.kenyan_intent.types import TranscriptKind

                svc = get_realtime_intent_service()
                result, route = svc.infer_sync(
                    self.session_id, text, kind=TranscriptKind.FINAL
                )
            else:
                result, route = await infer_caller_intent(
                    self.session_id, text, is_final=is_final
                )
        if route is not None:
            self._last_route = route
        if result is not None and is_final:
            logger.debug(
                "kenyan intent session={} intent={} confidence={:.2f}",
                self.session_id[:8],
                result.intent.value,
                result.confidence,
            )

    async def _handle_call_routing(self) -> None:
        if self._last_route is None or not self.session_id:
            return
        from api.services.call_routing.integration import route_call_from_intent

        language = "mixed"
        if self._last_route.metadata:
            language = self._last_route.metadata.get("language", "mixed")

        result = await route_call_from_intent(
            self._last_route,
            session_id=self.session_id,
            organization_id=self.organization_id,
            workflow_run_id=self.workflow_run_id,
            phone_e164=self.phone_e164,
            customer_name=self.customer_name,
            language=language,
        )
        if result is not None:
            self._last_routing = result
            logger.debug(
                "call routing session={} status={}",
                self.session_id[:8],
                result.status.value,
            )

    async def _handle_voice_mpesa_turn(self, user_text: str) -> None:
        engine = self.voice_mpesa
        if engine is None:
            return

        intent = None
        slots: dict[str, str] = {}
        from api.services.kenyan_intent.integration import voice_mpesa_intent_from_route

        mpesa_intent = voice_mpesa_intent_from_route(self._last_route)
        if mpesa_intent:
            intent = mpesa_intent
            if self._last_route is not None:
                slots = dict(self._last_route.slots)
        elif self.memory is not None and self.session_id:
            snap = self.memory.session(self.session_id).snapshot()
            intent = snap.intent.current.value
            slots = dict(snap.intent.slots)

        if engine.get_session(self.session_id) is None and intent:
            await engine.register_from_memory(
                session_id=self.session_id,
                organization_id=self.organization_id,
                workflow_run_id=self.workflow_run_id,
                phone_e164=self.phone_e164,
                customer_name=self.customer_name,
                intent=intent,
                slots=slots,
            )

        await engine.on_user_utterance(
            self.session_id,
            user_text,
            intent=intent,
            slots=slots,
            interrupted=self.recovery.was_interrupted(),
        )


@dataclass
class LLMResponseHandler:
    """Stream LLM tokens, push text to TTS, emit audio with minimal buffering."""

    llm: StreamingLLMBridge
    tts: StreamingTTSBridge
    transport: RealtimeAudioMediaTransport
    queues: PipelineQueues
    cancellation: InterruptionCancellationManager
    recovery: ConversationRecoveryManager
    latency: PipelineLatencyTracker
    config: RealtimeVoicePipelineConfig
    transcript_handler: TranscriptEventHandler
    stop: asyncio.Event
    behavior: KenyanConversationBehavior | None = None
    memory: RealtimeConversationMemoryService | None = None
    voice_mpesa: VoiceMpesaWorkflowEngine | None = None
    kenyan_intent_enabled: bool = False
    call_routing_enabled: bool = False
    session_id: str = ""
    _tts_text_pushed: bool = False

    async def run(self) -> None:
        while not self.stop.is_set():
            await self.transcript_handler.wait_for_turn()
            if self.stop.is_set():
                break
            await self._run_turn()

    async def _run_turn(self) -> None:
        if self.voice_mpesa is not None and self.session_id:
            prompt = self.voice_mpesa.consume_pending_prompt(self.session_id)
            if prompt:
                await self._speak_direct(prompt)
                return

        messages = self.recovery.messages_for_generation()
        was_interrupted = self.recovery.was_interrupted()
        partial = self.recovery.partial_assistant_text()
        turn_ctx = None
        if self.behavior is not None:
            turn_ctx = self.behavior.begin_turn(
                was_interrupted=was_interrupted,
                partial_spoken=partial,
            )
            messages = self.behavior.prepare_messages(messages, turn_ctx)
            if was_interrupted:
                pause_ms = self.behavior.pause_before_resume_ms(turn_ctx)
                if pause_ms > 0:
                    await asyncio.sleep(pause_ms / 1000.0)

        if self.memory is not None and self.session_id:
            messages, _mem = await self.memory.prepare_messages(self.session_id, messages)

        if self.voice_mpesa is not None and self.session_id:
            hint = self.voice_mpesa.system_hint(self.session_id)
            if hint:
                messages = [
                    LLMMessage(role="system", content=hint),
                    *messages,
                ]

        if self.kenyan_intent_enabled and self.transcript_handler._last_route:
            from api.services.kenyan_intent.integration import system_hint_from_route

            intent_hint = system_hint_from_route(self.transcript_handler._last_route)
            if intent_hint:
                messages = [
                    LLMMessage(role="system", content=intent_hint),
                    *messages,
                ]

        if self.call_routing_enabled and self.transcript_handler._last_routing:
            from api.services.call_routing.integration import system_hint_from_routing

            routing_hint = system_hint_from_routing(self.transcript_handler._last_routing)
            if routing_hint:
                messages = [
                    LLMMessage(role="system", content=routing_hint),
                    *messages,
                ]

        routing_prompt = None
        if self.call_routing_enabled and self.session_id:
            from api.services.call_routing.orchestrator import get_call_routing_orchestrator

            routing_prompt = get_call_routing_orchestrator().consume_voice_prompt(
                self.session_id
            )
        if routing_prompt:
            await self._speak_direct(routing_prompt)
            return

        user_msgs = [m for m in messages if m.role == "user"]
        user_text = user_msgs[-1].content if user_msgs else ""
        turn_count = len(user_msgs)

        from api.constants import VOICE_COST_OPTIMIZATION_ENABLED
        from api.services.voice_cost_optimization.types import ResponseSource

        cost_resolution = None
        if VOICE_COST_OPTIMIZATION_ENABLED and user_text:
            from api.services.voice_cost_optimization.service import (
                get_voice_cost_optimization_service,
            )

            cost_svc = get_voice_cost_optimization_service()
            intent = ""
            intent_confidence = 0.0
            if self.kenyan_intent_enabled and self.transcript_handler._last_route:
                intent = self.transcript_handler._last_route.intent.value
                intent_confidence = self.transcript_handler._last_route.confidence

            cost_svc.tracker().session(
                self.session_id,
                organization_id=self.config.organization_id,
            )
            cost_resolution = await cost_svc.resolve_turn(
                user_text,
                organization_id=self.config.organization_id,
                session_id=self.session_id,
                locale=self.config.payment_language,
                turn_count=turn_count,
                intent=intent,
                intent_confidence=intent_confidence,
            )
            cost_svc.tracker().record_hybrid_resolution(
                self.session_id,
                cost_resolution,
                user_text=user_text,
            )

            if cost_resolution.source in (
                ResponseSource.PRERECORDED,
                ResponseSource.CACHE,
            ):
                await self._speak_direct(
                    cost_resolution.text,
                    tts_cached=cost_resolution.tts_cached,
                )
                return

            if cost_resolution.routing is not None:
                await self.llm.apply_turn_budget(
                    cost_resolution.routing.max_output_tokens
                )

        self.recovery.begin_assistant_turn()
        self._tts_text_pushed = False
        self.latency.mark("llm_turn_start")

        tts_gid = await self.tts.begin_synthesis()

        self.cancellation.mark_llm_active()
        self.cancellation.mark_bot_speaking(generation_id=tts_gid)

        sink = self.tts.register_generation_sink(tts_gid)
        if self.cancellation.tts_stop is not None:
            self.cancellation.tts_stop.track_generation(tts_gid, sink)

        playback_task = asyncio.create_task(
            self._playback_loop(sink), name="tts-playback"
        )

        full_text: list[str] = []
        interrupted = False
        first_token = True
        try:
            async for stream_event in self.llm.generate(messages):
                if self.stop.is_set() or self.cancellation.is_turn_cancelled():
                    interrupted = True
                    break

                if stream_event.kind == LLMStreamKind.TEXT_DELTA and stream_event.text:
                    token = stream_event.text
                    if self.behavior is not None:
                        token = self.behavior.transform_token(token)
                    if not token:
                        continue
                    if first_token:
                        self.latency.mark("llm_first_token")
                        first_token = False
                    full_text.append(token)
                    self.recovery.append_assistant_delta(token)
                    if self.behavior is None and (
                        self.config.flush_tts_on_token
                        and len(token) >= self.config.min_tts_push_chars
                    ):
                        if not self._tts_text_pushed:
                            self.latency.mark("tts_first_text")
                            self._tts_text_pushed = True
                        await self.tts.push_text_delta(
                            token, generation_id=tts_gid
                        )
                elif stream_event.kind == LLMStreamKind.TEXT_DONE:
                    text = stream_event.text or "".join(full_text)
                    if self.behavior is not None and turn_ctx is not None:
                        text = self.behavior.transform_response(text, turn_ctx)
                        for chunk in self.behavior.tts_chunks(text, turn_ctx):
                            if not self._tts_text_pushed:
                                self.latency.mark("tts_first_text")
                            await self.tts.push_text_delta(
                                chunk.text, generation_id=tts_gid
                            )
                            self._tts_text_pushed = True
                            if chunk.pause_after_ms > 0:
                                await asyncio.sleep(chunk.pause_after_ms / 1000.0)
                    elif not self._tts_text_pushed and text:
                        await self.tts.push_text_delta(text, generation_id=tts_gid)
                        self._tts_text_pushed = True
                    self.recovery.complete_assistant_turn(text)
                    self.latency.mark("llm_done")
                    await self._record_llm_cost(
                        user_text=user_text,
                        output_text=text,
                        cost_resolution=cost_resolution,
                    )
                    break
        except asyncio.CancelledError:
            interrupted = True
            raise
        finally:
            if (interrupted or self.cancellation.is_turn_cancelled()) and (
                not self.cancellation.recovery_handled
            ):
                self.recovery.on_interruption(
                    partial_assistant="".join(full_text) or None
                )
                if self.memory is not None and self.session_id:
                    self.memory.session(self.session_id).on_interruption(
                        "".join(full_text) or ""
                    )
                    if "".join(full_text):
                        self.memory.session(self.session_id).on_assistant_complete(
                            "".join(full_text), interrupted=True
                        )
            else:
                await self.tts.end_synthesis(tts_gid)
                if self.memory is not None and self.session_id:
                    final_text = "".join(full_text)
                    if final_text:
                        self.memory.session(self.session_id).on_assistant_complete(
                            final_text, interrupted=False
                        )

            playback_task.cancel()
            await asyncio.gather(playback_task, return_exceptions=True)
            self.tts.release_generation_sink(tts_gid)
            if self.cancellation.tts_stop is not None:
                self.cancellation.tts_stop.clear_tracking()
            self.cancellation.mark_llm_idle()
            self.cancellation.mark_bot_idle()
            if not self.cancellation.recovery_handled:
                self.recovery.resume_after_interrupt()
            self.latency.record_turn_complete()

    async def _record_llm_cost(
        self,
        *,
        user_text: str,
        output_text: str,
        cost_resolution,
    ) -> None:
        from api.constants import VOICE_COST_OPTIMIZATION_ENABLED

        if not VOICE_COST_OPTIMIZATION_ENABLED or not self.session_id:
            return
        from api.services.voice_cost_optimization.service import (
            get_voice_cost_optimization_service,
        )

        svc = get_voice_cost_optimization_service()
        max_tokens = (
            cost_resolution.routing.max_output_tokens
            if cost_resolution and cost_resolution.routing
            else None
        )
        svc.tracker().record_llm_response(
            self.session_id,
            output_text=output_text,
            max_output_tokens=max_tokens,
        )
        svc.tracker().record_tts(self.session_id, output_text)
        if user_text and output_text and self.config.organization_id > 0:
            await svc.store_llm_response(
                self.config.organization_id,
                user_text,
                output_text,
            )

    async def _speak_direct(self, text: str, *, tts_cached: bool = False) -> None:
        """Speak a prompt without an LLM round-trip."""
        self.recovery.begin_assistant_turn()
        self.latency.mark("llm_turn_start")
        tts_gid = await self.tts.begin_synthesis()
        self.cancellation.mark_bot_speaking(generation_id=tts_gid)
        sink = self.tts.register_generation_sink(tts_gid)
        if self.cancellation.tts_stop is not None:
            self.cancellation.tts_stop.track_generation(tts_gid, sink)
        playback_task = asyncio.create_task(
            self._playback_loop(sink), name="tts-payment-prompt"
        )
        try:
            await self.tts.push_text_delta(text, generation_id=tts_gid)
            self.recovery.complete_assistant_turn(text)
            if self.memory is not None and self.session_id:
                self.memory.session(self.session_id).on_assistant_complete(
                    text, interrupted=False
                )
            from api.constants import VOICE_COST_OPTIMIZATION_ENABLED

            if VOICE_COST_OPTIMIZATION_ENABLED and self.session_id:
                from api.services.voice_cost_optimization.service import (
                    get_voice_cost_optimization_service,
                )

                get_voice_cost_optimization_service().tracker().record_tts(
                    self.session_id, text, skipped=tts_cached
                )
        finally:
            playback_task.cancel()
            await asyncio.gather(playback_task, return_exceptions=True)
            self.tts.release_generation_sink(tts_gid)
            if self.cancellation.tts_stop is not None:
                self.cancellation.tts_stop.clear_tracking()
            self.cancellation.mark_bot_idle()
            self.latency.record_turn_complete()

    async def _playback_loop(self, sink: asyncio.Queue) -> None:
        first_byte = True
        outbound_marked = False
        while True:
            chunk = await sink.get()
            if chunk is None:
                break
            if self.cancellation.is_turn_cancelled():
                break
            if first_byte:
                self.latency.mark("tts_first_byte")
                first_byte = False
            if self.config.direct_outbound:
                await self.transport.emit_outbound(chunk)
                if not outbound_marked:
                    self.latency.mark("outbound_first_byte")
                    outbound_marked = True
            else:
                self.queues.put_outbound(chunk)


@dataclass
class ControlEventHandler:
    """Drain control bus and propagate interrupts."""

    queues: PipelineQueues
    cancellation: InterruptionCancellationManager
    detector: InterruptionDetector
    stop: asyncio.Event

    async def run(self) -> None:
        async for event in self.queues.iter_control():
            if self.stop.is_set():
                break
            if event.kind == PipelineControlKind.INTERRUPT:
                await self.cancellation.interrupt_all(reason=event.reason or "control")
                self.detector.mark_handled()
            elif event.kind == PipelineControlKind.SHUTDOWN:
                self.stop.set()


def build_vad(config: RealtimeVoicePipelineConfig) -> VoiceActivityDetector:
    return VoiceActivityDetector(
        config=VADConfig(
            energy_threshold=config.vad_energy_threshold,
            min_speech_frames=config.vad_min_speech_frames,
            hangover_frames=config.vad_hangover_frames,
            frame_ms=config.vad_frame_ms,
        )
    )
