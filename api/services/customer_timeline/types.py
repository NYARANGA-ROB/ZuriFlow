"""Customer timeline types and journey state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TimelineChannel(str, Enum):
    VOICE = "voice"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    WEB_CHAT = "web_chat"
    EMAIL = "email"
    PAYMENT = "payment"
    CAMPAIGN = "campaign"
    ESCALATION = "escalation"
    ORCHESTRATION = "orchestration"
    SYSTEM = "system"


class CustomerJourneyState(str, Enum):
    """Cross-channel customer journey phase."""

    UNKNOWN = "unknown"
    IDLE = "idle"
    VOICE_ACTIVE = "voice_active"
    VOICE_COMPLETED = "voice_completed"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_FAILED = "payment_failed"
    WHATSAPP_FOLLOW_UP = "whatsapp_follow_up"
    EMAIL_FOLLOW_UP = "email_follow_up"
    CAMPAIGN_RETRY = "campaign_retry"
    ESCALATED = "escalated"
    ORCHESTRATION_WAITING = "orchestration_waiting"


@dataclass
class TimelineEntry:
    id: int
    organization_id: int
    customer_id: int | None
    phone_e164: str
    channel: TimelineChannel
    event_type: str
    title: str
    summary: str | None
    payload: dict[str, Any]
    workflow_run_id: int | None
    conversation_id: int | None
    transaction_id: int | None
    correlation_id: str | None
    journey_state: CustomerJourneyState | None
    occurred_at: str
    platform_event_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "customer_id": self.customer_id,
            "phone_e164": self.phone_e164,
            "channel": self.channel.value,
            "event_type": self.event_type,
            "title": self.title,
            "summary": self.summary,
            "payload": dict(self.payload),
            "workflow_run_id": self.workflow_run_id,
            "conversation_id": self.conversation_id,
            "transaction_id": self.transaction_id,
            "correlation_id": self.correlation_id,
            "journey_state": self.journey_state.value if self.journey_state else None,
            "occurred_at": self.occurred_at,
            "platform_event_id": self.platform_event_id,
        }


@dataclass
class CustomerTimeline:
    organization_id: int
    customer_id: int | None
    phone_e164: str
    customer_uuid: str | None
    full_name: str | None
    journey_state: CustomerJourneyState
    entries: list[TimelineEntry] = field(default_factory=list)
    channels_active: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "customer_id": self.customer_id,
            "phone_e164": self.phone_e164,
            "customer_uuid": self.customer_uuid,
            "full_name": self.full_name,
            "journey_state": self.journey_state.value,
            "channels_active": list(self.channels_active),
            "entries": [e.to_dict() for e in self.entries],
            "entry_count": len(self.entries),
        }
