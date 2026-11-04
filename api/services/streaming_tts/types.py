"""Streaming TTS value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TTSStreamKind(str, Enum):
    SYNTHESIS_START = "synthesis_start"
    AUDIO_CHUNK = "audio_chunk"
    SYNTHESIS_END = "synthesis_end"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True)
class TTSStreamEvent:
    kind: TTSStreamKind
    generation_id: str = ""
    audio: bytes | None = None
    sample_rate: int = 16000
    is_final: bool = False
    text_offset: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextFragment:
    """Incremental text pushed for partial-response playback."""

    text: str
    generation_id: str
    is_final: bool = False
