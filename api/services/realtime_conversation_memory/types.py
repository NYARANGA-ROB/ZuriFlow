"""Types for realtime conversation memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CallIntent(str, Enum):
    UNKNOWN = "unknown"
    GREETING = "greeting"
    REQUEST_BALANCE = "request_balance"
    REQUEST_PAYMENT = "request_payment"
    REQUEST_SUPPORT = "request_support"
    ACCOUNT_INQUIRY = "account_inquiry"
    CONFIRMATION = "confirmation"
    GRATITUDE = "gratitude"
    FAREWELL = "farewell"
    INTERRUPTION = "interruption"


class TurnStatus(str, Enum):
    COMPLETE = "complete"
    INTERRUPTED = "interrupted"
    PARTIAL = "partial"


@dataclass
class IntentState:
    current: CallIntent = CallIntent.UNKNOWN
    confidence: float = 0.0
    slots: dict[str, str] = field(default_factory=dict)
    history: list[CallIntent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current.value,
            "confidence": round(self.confidence, 3),
            "slots": dict(self.slots),
            "history": [h.value for h in self.history[-5:]],
        }


@dataclass
class TurnRecord:
    turn_id: int
    user_text: str
    assistant_text: str = ""
    status: TurnStatus = TurnStatus.COMPLETE
    intent: CallIntent = CallIntent.UNKNOWN
    interrupted: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user": self.user_text,
            "assistant": self.assistant_text,
            "status": self.status.value,
            "intent": self.intent.value,
            "interrupted": self.interrupted,
        }


@dataclass
class MemorySnapshot:
    session_id: str
    turns: list[TurnRecord]
    summary: str
    intent: IntentState
    interrupted: bool
    partial_assistant: str
    pause_duration_s: float
    last_activity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_count": len(self.turns),
            "summary": self.summary,
            "intent": self.intent.to_dict(),
            "interrupted": self.interrupted,
            "partial_assistant": self.partial_assistant,
            "pause_duration_s": round(self.pause_duration_s, 2),
            "turns": [t.to_dict() for t in self.turns[-6:]],
        }


@dataclass(frozen=True)
class RetrievalResult:
    session_id: str
    context_block: str
    summary: str
    intent: CallIntent
    intent_confidence: float
    slots: dict[str, str]
    recent_turns: list[TurnRecord]
    latency_ms: float
    recovered_from_pause: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "context_block": self.context_block,
            "summary": self.summary,
            "intent": self.intent.value,
            "intent_confidence": round(self.intent_confidence, 3),
            "slots": dict(self.slots),
            "latency_ms": round(self.latency_ms, 3),
            "recovered_from_pause": self.recovered_from_pause,
            "recent_turns": [t.to_dict() for t in self.recent_turns],
        }
