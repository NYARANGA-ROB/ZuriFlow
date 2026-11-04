"""Streaming LLM value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResponseStreamKind(str, Enum):
    GENERATION_START = "generation_start"
    TOKEN_DELTA = "token_delta"
    SENTENCE_PARTIAL = "sentence_partial"
    GENERATION_END = "generation_end"
    CANCELLED = "cancelled"
    ERROR = "error"
    TOOL_CALL = "tool_call"


@dataclass(frozen=True)
class ResponseStreamEvent:
    kind: ResponseStreamKind
    generation_id: str
    text: str = ""
    delta: str = ""
    is_final: bool = False
    response_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str
    message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
