"""Types for Kenyan conversational behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LanguageMode(str, Enum):
    ENGLISH = "english"
    SWAHILI = "swahili"
    MIXED = "mixed"


@dataclass(frozen=True)
class StyledChunk:
    text: str
    pause_after_ms: int = 0
    is_confirmation: bool = False


@dataclass
class TurnContext:
    """Per-turn state for style middleware and pacing."""

    was_interrupted: bool = False
    partial_spoken: str = ""
    interrupt_reason: str = ""
    turn_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
