"""Types for human escalation and operator handoff."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EscalationStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    CLAIMED = "claimed"
    TRANSFERRING = "transferring"
    CONNECTED = "connected"
    RESOLVED = "resolved"
    FAILED = "failed"


@dataclass
class HandoffPackage:
    """Conversation context preserved for human agents."""

    session_id: str
    organization_id: int
    workflow_run_id: int = 0
    phone_e164: str = ""
    customer_name: str = ""
    customer_id: int | None = None
    intent: str = "escalation"
    reason: str = ""
    language: str = "mixed"
    summary: str = ""
    transcript_excerpt: list[dict[str, Any]] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    priority: int = 50
    risk_level: str = "medium"
    call_sid: str = ""
    queue_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "phone_e164": self.phone_e164,
            "customer_name": self.customer_name,
            "customer_id": self.customer_id,
            "intent": self.intent,
            "reason": self.reason,
            "language": self.language,
            "summary": self.summary,
            "transcript_excerpt": list(self.transcript_excerpt),
            "slots": dict(self.slots),
            "priority": self.priority,
            "risk_level": self.risk_level,
            "call_sid": self.call_sid,
            "queue_name": self.queue_name,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandoffPackage:
        return cls(
            session_id=str(data["session_id"]),
            organization_id=int(data["organization_id"]),
            workflow_run_id=int(data.get("workflow_run_id", 0)),
            phone_e164=str(data.get("phone_e164", "")),
            customer_name=str(data.get("customer_name", "")),
            customer_id=data.get("customer_id"),
            intent=str(data.get("intent", "escalation")),
            reason=str(data.get("reason", "")),
            language=str(data.get("language", "mixed")),
            summary=str(data.get("summary", "")),
            transcript_excerpt=list(data.get("transcript_excerpt") or []),
            slots=dict(data.get("slots") or {}),
            priority=int(data.get("priority", 50)),
            risk_level=str(data.get("risk_level", "medium")),
            call_sid=str(data.get("call_sid", "")),
            queue_name=str(data.get("queue_name", "")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class OperatorClaim:
    session_id: str
    organization_id: int
    queue_name: str
    operator_id: int
    claimed_at: float
    handoff: HandoffPackage

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "queue_name": self.queue_name,
            "operator_id": self.operator_id,
            "claimed_at": self.claimed_at,
            "handoff": self.handoff.to_dict(),
        }
