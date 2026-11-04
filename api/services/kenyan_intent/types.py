from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BusinessIntent(str, Enum):
    UNKNOWN = "unknown"
    PAYMENT = "payment"
    BALANCE_INQUIRY = "balance_inquiry"
    BOOKING = "booking"
    APPOINTMENT = "appointment"
    DELIVERY = "delivery"
    ORDER = "order"
    COMPLAINT = "complaint"
    ESCALATION = "escalation"
    ACCOUNT_INQUIRY = "account_inquiry"
    LOCATION_INQUIRY = "location_inquiry"
    CANCELLATION = "cancellation"
    CONFIRMATION = "confirmation"
    SUPPORT = "support"
    CALLBACK = "callback"
    INTERRUPTION = "interruption"


class RouteAction(str, Enum):
    NONE = "none"
    TRIGGER_MPESA_PAYMENT = "trigger_mpesa_payment"
    TRIGGER_BOOKING = "trigger_booking"
    TRIGGER_ESCALATION = "trigger_escalation"
    ROUTE_SUPPORT = "route_support"
    SCHEDULE_CALLBACK = "schedule_callback"
    CONTINUE = "continue_conversation"


class TranscriptKind(str, Enum):
    PARTIAL = "partial"
    FINAL = "final"


@dataclass
class IntentMatch:
    intent: BusinessIntent
    confidence: float
    matched_phrases: list[str] = field(default_factory=list)
    language: str = "mixed"


@dataclass
class ClassificationResult:
    intent: BusinessIntent
    confidence: float
    slots: dict[str, str] = field(default_factory=dict)
    language: str = "mixed"
    matched_phrases: list[str] = field(default_factory=list)
    normalized_text: str = ""
    original_text: str = ""
    latency_ms: float = 0.0
    is_partial: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 4),
            "slots": dict(self.slots),
            "language": self.language,
            "matched_phrases": list(self.matched_phrases),
            "normalized_text": self.normalized_text,
            "original_text": self.original_text,
            "latency_ms": round(self.latency_ms, 3),
            "is_partial": self.is_partial,
        }


@dataclass
class RouteDecision:
    action: RouteAction
    intent: BusinessIntent
    confidence: float
    priority: int
    reason: str
    slots: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "intent": self.intent.value,
            "confidence": round(self.confidence, 4),
            "priority": self.priority,
            "reason": self.reason,
            "slots": dict(self.slots),
            "metadata": dict(self.metadata),
        }


@dataclass
class IntentSessionState:
    session_id: str
    current_intent: BusinessIntent = BusinessIntent.UNKNOWN
    confidence: float = 0.0
    slots: dict[str, str] = field(default_factory=dict)
    history: list[BusinessIntent] = field(default_factory=list)
    interrupted: bool = False
    partial_buffer: str = ""
    language: str = "mixed"
    last_result: ClassificationResult | None = None
    last_route: RouteDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "current_intent": self.current_intent.value,
            "confidence": round(self.confidence, 4),
            "slots": dict(self.slots),
            "history": [h.value for h in self.history[-8:]],
            "interrupted": self.interrupted,
            "partial_buffer": self.partial_buffer,
            "language": self.language,
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "last_route": self.last_route.to_dict() if self.last_route else None,
        }
