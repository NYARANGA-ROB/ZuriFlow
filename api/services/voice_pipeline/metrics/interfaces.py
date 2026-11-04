"""Metrics collection contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class MetricName(str, Enum):
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    STT_FINAL = "stt_final"
    LLM_FIRST_TOKEN = "llm_first_token"
    LLM_DONE = "llm_done"
    TTS_FIRST_BYTE = "tts_first_byte"
    TTS_DONE = "tts_done"
    USER_TO_BOT_LATENCY = "user_to_bot_latency"
    STAGE_DURATION = "stage_duration"
    TURN_E2E_LATENCY = "turn_e2e_latency"
    WS_ROUNDTRIP = "ws_roundtrip"
    QUEUE_BACKPRESSURE = "queue_backpressure"
    PACKET_LOSS = "packet_loss"
    ERROR = "error"


@dataclass(frozen=True)
class MetricEvent:
    name: MetricName
    workflow_run_id: int
    timestamp_ms: float
    value: float | None = None
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricsSnapshot:
    workflow_run_id: int
    events: list[MetricEvent] = field(default_factory=list)
    counters: dict[str, float] = field(default_factory=dict)
    durations_ms: dict[str, float] = field(default_factory=dict)


class MetricsCollector(Protocol):
    """Non-blocking metrics sink."""

    async def record(self, event: MetricEvent) -> None: ...

    def snapshot(self) -> MetricsSnapshot: ...
