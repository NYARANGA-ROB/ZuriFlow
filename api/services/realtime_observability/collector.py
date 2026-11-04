"""Bridges pipeline events to Prometheus metrics and structured logs."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from api.services.realtime_observability.logging import log_event
from api.services.realtime_observability.metrics import (
    ACTIVE_SESSIONS,
    CALL_STARTUP_MS,
    E2E_LATENCY_MS,
    FIRST_RESPONSE_MS,
    INTENT_MS,
    INTERRUPTIONS_TOTAL,
    LLM_FIRST_TOKEN_MS,
    LLM_TOTAL_MS,
    NORMALIZE_MS,
    RECONNECTS_TOTAL,
    STT_RESPONSE_MS,
    TOOL_CALL_MS,
    TTS_FIRST_BYTE_MS,
    TTS_GENERATION_MS,
    TURNS_TOTAL,
    WORKFLOW_STAGE_MS,
    WS_CONNECT_MS,
    WS_CONNECTIONS_TOTAL,
    WS_DISCONNECTS_TOTAL,
    WS_ROUNDTRIP_MS,
)
from api.services.realtime_observability.percentiles import record_stage_ms
from api.services.realtime_observability.tracing import TRACING
from api.services.voice_pipeline.metrics.interfaces import (
    MetricEvent,
    MetricName,
    MetricsCollector,
    MetricsSnapshot,
)


@dataclass
class VoiceObservabilityCollector:
    """Non-blocking metrics sink for realtime voice pipelines."""

    workflow_run_id: int
    endpoint: str = "realtime_voice"
    session_id: str = ""
    _events: list[MetricEvent] = field(default_factory=list)
    _counters: dict[str, float] = field(default_factory=dict)
    _durations_ms: dict[str, float] = field(default_factory=dict)
    _queue: asyncio.Queue[MetricEvent | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=512)
    )
    _worker: asyncio.Task | None = None
    _turn_start_mono: float | None = None

    async def start(self) -> None:
        self._worker = asyncio.create_task(self._consume(), name="voice-observability")

    async def stop(self) -> None:
        await self._queue.put(None)
        if self._worker:
            await self._worker

    async def record(self, event: MetricEvent) -> None:
        await self._queue.put(event)

    def record_fast(self, event: MetricEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(
            workflow_run_id=self.workflow_run_id,
            events=list(self._events),
            counters=dict(self._counters),
            durations_ms=dict(self._durations_ms),
        )

    def bind_session(self, session_id: str) -> None:
        self.session_id = session_id

    def begin_turn(self) -> None:
        self._turn_start_mono = time.monotonic()

    def record_turn_stage(self, stage: str, *, value_ms: float | None = None) -> None:
        if value_ms is None and self._turn_start_mono is not None:
            value_ms = (time.monotonic() - self._turn_start_mono) * 1000.0
        if value_ms is None:
            return
        with TRACING.span(stage, session_id=self.session_id, latency_ms=value_ms):
            pass
        record_stage_ms(stage, value_ms)
        if stage == "stt_final":
            STT_RESPONSE_MS.observe(value_ms)
            record_stage_ms("stt", value_ms)
        elif stage == "normalize":
            NORMALIZE_MS.observe(value_ms)
        elif stage == "intent":
            INTENT_MS.observe(value_ms)
        elif stage == "workflow":
            WORKFLOW_STAGE_MS.observe(value_ms)
        elif stage == "tool_call":
            TOOL_CALL_MS.observe(value_ms)
        elif stage == "llm_first_token":
            LLM_FIRST_TOKEN_MS.observe(value_ms)
        elif stage == "tts_first_byte":
            TTS_FIRST_BYTE_MS.observe(value_ms)
            FIRST_RESPONSE_MS.observe(value_ms)
        elif stage == "call_startup":
            CALL_STARTUP_MS.observe(value_ms)
        elif stage == "turn_e2e":
            E2E_LATENCY_MS.observe(value_ms)

    def record_turn_complete(self, stages: dict[str, float | None], *, interrupted: bool = False) -> None:
        status = "interrupted" if interrupted else "completed"
        TURNS_TOTAL.inc(status=status)
        e2e = stages.get("turn_e2e_ms")
        if e2e is not None:
            E2E_LATENCY_MS.observe(e2e)
            log_event(
                "turn.complete",
                session_id=self.session_id,
                workflow_run_id=self.workflow_run_id,
                e2e_ms=round(e2e, 2),
                status=status,
                **{k: round(v, 2) for k, v in stages.items() if v is not None},
            )
        llm_total = stages.get("llm_to_tts_start_ms")
        if llm_total is not None:
            LLM_TOTAL_MS.observe(llm_total)
        tts_gen = stages.get("tts_to_audio_ms")
        if tts_gen is not None:
            TTS_GENERATION_MS.observe(tts_gen)

    @staticmethod
    def record_ws_handshake(latency_ms: float) -> None:
        WS_CONNECT_MS.observe(latency_ms)
        record_stage_ms("websocket_connect", latency_ms)

    @staticmethod
    def record_ws_connect(*, endpoint: str, session_id: str, resumed: bool) -> None:
        WS_CONNECTIONS_TOTAL.inc(endpoint=endpoint)
        if resumed:
            RECONNECTS_TOTAL.inc(endpoint=endpoint)
        ACTIVE_SESSIONS.inc(endpoint=endpoint)
        log_event(
            "ws.connect",
            session_id=session_id,
            endpoint=endpoint,
            resumed=resumed,
        )

    @staticmethod
    def record_ws_disconnect(*, endpoint: str, session_id: str, reason: str) -> None:
        WS_DISCONNECTS_TOTAL.inc(endpoint=endpoint, reason=reason[:32])
        ACTIVE_SESSIONS.dec(endpoint=endpoint)
        log_event(
            "ws.disconnect",
            session_id=session_id,
            endpoint=endpoint,
            reason=reason,
        )

    @staticmethod
    def record_ws_roundtrip(latency_ms: float, *, endpoint: str = "realtime_audio") -> None:
        WS_ROUNDTRIP_MS.observe(latency_ms)
        record_stage_ms("websocket_rtt", latency_ms)

    @staticmethod
    def record_interruption(*, source: str, session_id: str = "") -> None:
        INTERRUPTIONS_TOTAL.inc(source=source)
        log_event("interruption", session_id=session_id, source=source)

    async def _consume(self) -> None:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            self._events.append(event)
            key = event.name.value
            self._counters[key] = self._counters.get(key, 0.0) + 1.0
            if event.value is not None:
                self._durations_ms[key] = event.value
                self._export_pipeline_event(event)

    def _export_pipeline_event(self, event: MetricEvent) -> None:
        value = event.value
        if value is None:
            return
        stage = event.labels.get("stage", "")
        if event.name == MetricName.USER_TO_BOT_LATENCY:
            E2E_LATENCY_MS.observe(value)
        elif event.name == MetricName.STAGE_DURATION:
            if stage == "llm_first_token":
                LLM_FIRST_TOKEN_MS.observe(value)
            elif stage == "tts_first_byte":
                TTS_FIRST_BYTE_MS.observe(value)
            elif stage == "stt_final":
                STT_RESPONSE_MS.observe(value)
