from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WhatsAppProviderName(str, Enum):
    META = "meta"
    TWILIO = "twilio"


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    CLOSED = "closed"


class WhatsAppTemplateName(str, Enum):
    CALL_SUMMARY = "call_summary"
    PAYMENT_LINK = "payment_link"
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    ESCALATION_HANDOFF = "escalation_handoff"
    GENERIC_TEXT = "generic_text"


@dataclass(frozen=True)
class SendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InboundMessage:
    from_phone: str
    body: str
    provider_message_id: str | None = None
    profile_name: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundPayload:
    organization_id: int
    phone_e164: str
    body: str
    provider: WhatsAppProviderName
    template_name: str | None = None
    conversation_id: int | None = None
    message_id: int | None = None
    workflow_run_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attempt: int = 1
