"""Shared value types for the modular voice pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TranscriptKind(str, Enum):
    PARTIAL = "partial"
    FINAL = "final"
    SPEECH_START = "speech_start"


class LLMStreamKind(str, Enum):
    TEXT_DELTA = "text_delta"
    TEXT_DONE = "text_done"
    TOOL_CALL = "tool_call"


@dataclass(frozen=True)
class AudioChunk:
    """PCM audio payload flowing between pipeline stages."""

    pcm: bytes
    sample_rate: int
    channels: int = 1
    timestamp_ms: float | None = None


@dataclass(frozen=True)
class TranscriptEvent:
    text: str
    kind: TranscriptKind
    confidence: float | None = None
    language: str | None = None


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMStreamEvent:
    kind: LLMStreamKind
    text: str = ""
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None


@dataclass(frozen=True)
class TTSRequest:
    text: str
    voice: str | None = None
    sample_rate: int | None = None


@dataclass(frozen=True)
class InboundCallContext:
    """Normalized context produced when an inbound call is accepted."""

    provider: str
    call_id: str
    workflow_id: int
    workflow_run_id: int
    user_id: int
    organization_id: int
    caller_number: str
    called_number: str
    telephony_configuration_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VoicePipelineConfig:
    """Runtime configuration for a single voice session."""

    workflow_id: int
    workflow_run_id: int
    user_id: int
    organization_id: int
    provider_name: str
    call_id: str
    sample_rate: int = 16000
    is_realtime: bool = False
    telephony_configuration_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)
