"""Typed platform event schema."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlatformEventType(str, Enum):
    # Call / workflow lifecycle
    CALL_COMPLETED = "call.completed"
    CALL_FAILED = "call.failed"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_TIMEOUT = "workflow.timeout"

    # Payments
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_TIMEOUT = "payment.timeout"

    # Campaigns
    CAMPAIGN_RETRY_NEEDED = "campaign.retry_needed"
    CAMPAIGN_BATCH_COMPLETED = "campaign.batch_completed"
    CAMPAIGN_COMPLETED = "campaign.completed"

    # Escalations & routing
    ESCALATION_CREATED = "escalation.created"
    ESCALATION_RESOLVED = "escalation.resolved"

    # Omnichannel
    WHATSAPP_MESSAGE_SENT = "whatsapp.message_sent"
    WHATSAPP_MESSAGE_FAILED = "whatsapp.message_failed"
    EMAIL_SENT = "email.sent"
    EMAIL_FAILED = "email.failed"

    # Durable orchestration
    ORCHESTRATION_STARTED = "orchestration.started"
    ORCHESTRATION_SIGNAL = "orchestration.signal"
    ORCHESTRATION_COMPLETED = "orchestration.completed"
    ORCHESTRATION_FAILED = "orchestration.failed"


class PlatformEventSource(str, Enum):
    WORKFLOW_COMPLETION = "workflow_completion"
    TELEPHONY = "telephony"
    MPESA = "mpesa"
    CAMPAIGN = "campaign"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    DURABLE_EXECUTION = "durable_execution"
    API = "api"
    SYSTEM = "system"


@dataclass
class PlatformEvent:
    event_type: PlatformEventType
    organization_id: int | None
    source: PlatformEventSource | str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    idempotency_key: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "organization_id": self.organization_id,
            "source": (
                self.source.value
                if isinstance(self.source, PlatformEventSource)
                else str(self.source)
            ),
            "correlation_id": self.correlation_id,
            "payload": dict(self.payload),
            "idempotency_key": self.idempotency_key,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlatformEvent:
        return cls(
            event_id=str(data.get("event_id") or uuid.uuid4()),
            event_type=PlatformEventType(data["event_type"]),
            organization_id=data.get("organization_id"),
            source=data.get("source", PlatformEventSource.SYSTEM.value),
            correlation_id=data.get("correlation_id"),
            payload=dict(data.get("payload") or {}),
            idempotency_key=data.get("idempotency_key"),
            timestamp=float(data.get("timestamp") or time.time()),
        )

    @classmethod
    def from_db_row(cls, row: Any) -> PlatformEvent:
        return cls(
            event_id=row.event_id,
            event_type=PlatformEventType(row.event_type),
            organization_id=row.organization_id,
            source=row.source,
            correlation_id=row.correlation_id,
            payload=dict(row.payload or {}),
            idempotency_key=row.idempotency_key,
            timestamp=row.created_at.timestamp() if row.created_at else time.time(),
        )
