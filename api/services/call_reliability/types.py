"""Types for production call reliability and recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReliabilityEventType(str, Enum):
    CALL_FAILED = "call_failed"
    CALL_RETRY_SCHEDULED = "call_retry_scheduled"
    WORKFLOW_INTERRUPTED = "workflow_interrupted"
    WORKFLOW_RECOVERED = "workflow_recovered"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    WEBSOCKET_RECONNECTED = "websocket_reconnected"
    TRANSCRIPT = "transcript"
    PAYMENT = "payment"
    ESCALATION = "escalation"
    CUSTOM = "custom"


class RecoveryKind(str, Enum):
    CALL_RETRY = "call_retry"
    WORKFLOW_RESUME = "workflow_resume"
    EVENT_REPLAY = "event_replay"
    WEBSOCKET_CHECKPOINT = "websocket_checkpoint"


class FailureSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ReliabilityEvent:
    event_id: str
    event_type: ReliabilityEventType
    organization_id: int
    session_id: str = ""
    workflow_run_id: int = 0
    timestamp: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "organization_id": self.organization_id,
            "session_id": self.session_id,
            "workflow_run_id": self.workflow_run_id,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReliabilityEvent:
        return cls(
            event_id=str(data["event_id"]),
            event_type=ReliabilityEventType(data["event_type"]),
            organization_id=int(data["organization_id"]),
            session_id=str(data.get("session_id", "")),
            workflow_run_id=int(data.get("workflow_run_id", 0)),
            timestamp=float(data.get("timestamp", 0.0)),
            payload=dict(data.get("payload") or {}),
            idempotency_key=str(data.get("idempotency_key", "")),
        )


@dataclass
class RetryJob:
    job_id: str
    organization_id: int
    kind: RecoveryKind
    workflow_run_id: int = 0
    session_id: str = ""
    attempt: int = 1
    max_attempts: int = 5
    scheduled_at: float = 0.0
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "organization_id": self.organization_id,
            "kind": self.kind.value,
            "workflow_run_id": self.workflow_run_id,
            "session_id": self.session_id,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "scheduled_at": self.scheduled_at,
            "reason": self.reason,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetryJob:
        return cls(
            job_id=str(data["job_id"]),
            organization_id=int(data["organization_id"]),
            kind=RecoveryKind(data["kind"]),
            workflow_run_id=int(data.get("workflow_run_id", 0)),
            session_id=str(data.get("session_id", "")),
            attempt=int(data.get("attempt", 1)),
            max_attempts=int(data.get("max_attempts", 5)),
            scheduled_at=float(data.get("scheduled_at", 0.0)),
            reason=str(data.get("reason", "")),
            payload=dict(data.get("payload") or {}),
        )


@dataclass
class FailureRecord:
    failure_id: str
    organization_id: int
    category: str
    severity: FailureSeverity
    message: str
    session_id: str = ""
    workflow_run_id: int = 0
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "organization_id": self.organization_id,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "session_id": self.session_id,
            "workflow_run_id": self.workflow_run_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
