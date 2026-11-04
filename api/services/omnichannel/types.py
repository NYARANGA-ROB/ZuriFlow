"""Shared types for the omnichannel engagement layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Channel(str, Enum):
    VOICE = "voice"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    WEB_CHAT = "web_chat"


class IdentityKind(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    CRM = "crm"
    CUSTOMER = "customer"
    WEB = "web"


class OrchestrationAction(str, Enum):
    SEND_SMS = "SEND_SMS"
    SEND_WHATSAPP = "SEND_WHATSAPP"
    START_CALL = "START_CALL"
    WAIT_FOR_REPLY = "WAIT_FOR_REPLY"
    SEND_RECEIPT = "SEND_RECEIPT"
    SEND_DOCUMENT = "SEND_DOCUMENT"
    ESCALATE = "ESCALATE"


class MessagePurpose(str, Enum):
    TRANSACTIONAL = "transactional"
    MARKETING = "marketing"


class FollowupTrigger(str, Enum):
    MISSED_CALL = "missed_call"
    PAYMENT_SUCCESS = "payment_success"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_TOMORROW = "appointment_tomorrow"
    HUMAN_REQUESTED = "human_requested"


@dataclass
class IdentityMatch:
    customer_id: int
    created: bool
    merged_from: list[int] = field(default_factory=list)
    identities: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "created": self.created,
            "merged_from": list(self.merged_from),
            "identities": list(self.identities),
        }


@dataclass
class ConsentDecision:
    allowed: bool
    reason: str
    legal_basis: str
    purpose: str
    channel: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "legal_basis": self.legal_basis,
            "purpose": self.purpose,
            "channel": self.channel,
        }


@dataclass
class ChannelSendResult:
    success: bool
    status: str
    provider_message_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "provider_message_id": self.provider_message_id,
            "error": self.error,
            "metadata": dict(self.metadata),
        }
