"""Streaming STT value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamingTranscriptKind(str, Enum):
    """Transcript event kinds emitted by the realtime STT pipeline."""

    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    PARTIAL = "partial"
    INCREMENTAL = "incremental"
    FINAL = "final"
    INTERRUPTED = "interrupted"
    ERROR = "error"
    PROVIDER_SWITCH = "provider_switch"


@dataclass(frozen=True)
class StreamingTranscriptEvent:
    text: str
    kind: StreamingTranscriptKind
    is_final: bool = False
    confidence: float | None = None
    language: str | None = None
    provider: str = ""
    start_ms: float | None = None
    end_ms: float | None = None
    # For INCREMENTAL: only the new suffix since the last partial
    delta: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class STTProviderStatus:
    active_provider: str
    deepgram_connected: bool
    fallback_active: bool
    reconnect_attempts: int
    last_event_age_ms: float | None = None
