"""Pipeline event types for queue-based orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from api.services.voice_pipeline.types import AudioChunk, LLMStreamEvent, TranscriptEvent


class PipelineStage(str, Enum):
    INBOUND = "inbound"
    STT = "stt"
    LLM = "llm"
    TTS = "tts"
    OUTBOUND = "outbound"


class PipelineControlKind(str, Enum):
    INTERRUPT = "interrupt"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class PipelineControlEvent:
    kind: PipelineControlKind
    reason: str = ""
    stage: PipelineStage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineEvent:
    """Unified event flowing through the pipeline control bus."""

    stage: PipelineStage
    transcript: TranscriptEvent | None = None
    llm: LLMStreamEvent | None = None
    audio: AudioChunk | None = None
    control: PipelineControlEvent | None = None
    generation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
