from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoutingDestination(str, Enum):
    AI_AGENT = "ai_agent"
    HUMAN_QUEUE = "human_queue"
    PAYMENT_FLOW = "payment_flow"
    BOOKING_QUEUE = "booking_queue"
    SUPPORT_QUEUE = "support_queue"
    CALLBACK_QUEUE = "callback_queue"
    FALLBACK_AI = "fallback_ai"
    VOICEMAIL = "voicemail"


class RoutingStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ESCALATING = "escalating"
    TRANSFERRED = "transferred"
    FALLBACK = "fallback"
    COMPLETED = "completed"
    FAILED = "failed"


class FallbackStrategy(str, Enum):
    CONTINUE_AI = "continue_ai"
    OFFER_CALLBACK = "offer_callback"
    VOICEMAIL = "voicemail"
    RETRY_QUEUE = "retry_queue"
    WHATSAPP_HANDOFF = "whatsapp_handoff"


@dataclass
class CallRoutingContext:
    session_id: str
    organization_id: int
    workflow_run_id: int = 0
    phone_e164: str = ""
    customer_name: str = "there"
    call_sid: str = ""
    language: str = "mixed"
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "phone_e164": self.phone_e164,
            "customer_name": self.customer_name,
            "call_sid": self.call_sid,
            "language": self.language,
            "provider": self.provider,
        }


@dataclass
class CallRoutingPlan:
    destination: RoutingDestination
    queue_name: str
    priority: int
    reason: str
    intent: str
    confidence: float
    language: str = "mixed"
    slots: dict[str, str] = field(default_factory=dict)
    voice_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "destination": self.destination.value,
            "queue_name": self.queue_name,
            "priority": self.priority,
            "reason": self.reason,
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "language": self.language,
            "slots": dict(self.slots),
            "voice_prompt": self.voice_prompt,
            "metadata": dict(self.metadata),
        }


@dataclass
class QueueEntry:
    session_id: str
    organization_id: int
    queue_name: str
    priority: int
    intent: str
    language: str
    enqueued_at: float
    workflow_run_id: int = 0
    phone_e164: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "queue_name": self.queue_name,
            "priority": self.priority,
            "intent": self.intent,
            "language": self.language,
            "enqueued_at": self.enqueued_at,
            "workflow_run_id": self.workflow_run_id,
            "phone_e164": self.phone_e164,
            "metadata": dict(self.metadata),
        }


@dataclass
class EscalationRequest:
    session_id: str
    organization_id: int
    reason: str
    intent: str
    language: str = "mixed"
    workflow_run_id: int = 0
    phone_e164: str = ""
    call_sid: str = ""
    context: str = ""
    queue_name: str = ""
    transfer_destination: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "reason": self.reason,
            "intent": self.intent,
            "language": self.language,
            "workflow_run_id": self.workflow_run_id,
            "phone_e164": self.phone_e164,
            "call_sid": self.call_sid,
            "context": self.context,
            "queue_name": self.queue_name,
            "transfer_destination": self.transfer_destination,
        }


@dataclass
class CallRoutingResult:
    status: RoutingStatus
    plan: CallRoutingPlan | None = None
    queue_position: int | None = None
    fallback_strategy: FallbackStrategy | None = None
    voice_prompt: str = ""
    escalated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "queue_position": self.queue_position,
            "fallback_strategy": (
                self.fallback_strategy.value if self.fallback_strategy else None
            ),
            "voice_prompt": self.voice_prompt,
            "escalated": self.escalated,
            "metadata": dict(self.metadata),
        }
