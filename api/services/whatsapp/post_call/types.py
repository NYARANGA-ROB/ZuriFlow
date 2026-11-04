from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PostCallStep(str, Enum):
    SUMMARIZE = "summarize"
    SEND_SUMMARY = "send_summary"
    SEND_PAYMENT_LINK = "send_payment_link"
    SEND_BOOKING_LINK = "send_booking_link"
    ESCALATE = "escalate"


class FollowUpAction(str, Enum):
    NONE = "none"
    PAYMENT = "payment"
    BOOKING = "booking"
    BOTH = "both"


@dataclass(frozen=True)
class PostCallSummary:
    text: str
    intent: str
    intent_confidence: float
    next_steps: str
    language: str
    slots: dict[str, str] = field(default_factory=dict)
    source: str = "memory"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "next_steps": self.next_steps,
            "language": self.language,
            "slots": dict(self.slots),
            "source": self.source,
        }


@dataclass
class StepResult:
    step: PostCallStep
    success: bool
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class PostCallWorkflowResult:
    workflow_run_id: int
    organization_id: int
    conversation_id: int | None = None
    phone_e164: str | None = None
    summary: PostCallSummary | None = None
    steps: list[StepResult] = field(default_factory=list)
    escalated: bool = False
    follow_up_action: FollowUpAction = FollowUpAction.NONE
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def success(self) -> bool:
        if self.skipped:
            return True
        return all(s.success for s in self.steps) if self.steps else False

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_run_id": self.workflow_run_id,
            "organization_id": self.organization_id,
            "conversation_id": self.conversation_id,
            "phone_e164": self.phone_e164,
            "summary": self.summary.to_dict() if self.summary else None,
            "steps": [
                {
                    "step": s.step.value,
                    "success": s.success,
                    "error": s.error,
                    "detail": s.detail,
                }
                for s in self.steps
            ],
            "escalated": self.escalated,
            "follow_up_action": self.follow_up_action.value,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "success": self.success,
        }
