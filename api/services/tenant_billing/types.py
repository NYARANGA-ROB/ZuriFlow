"""Domain types for multi-tenant usage billing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UsageMetric(str, Enum):
    CALL_MINUTES = "call_minutes"
    PHONE_CALLS = "phone_calls"
    WEB_CALLS = "web_calls"
    STT_SECONDS = "stt_seconds"
    TTS_CHARACTERS = "tts_characters"
    LLM_TOKENS = "llm_tokens"
    SMS = "sms"
    WHATSAPP_INBOUND = "whatsapp_inbound"
    WHATSAPP_OUTBOUND = "whatsapp_outbound"
    MPESA_TRANSACTION = "mpesa_transaction"
    MPESA_COLLECTED = "mpesa_collected"
    STORAGE_GB = "storage_gb"
    WORKFLOWS = "workflows"
    AGENTS = "agents"
    USERS = "users"
    INTEGRATIONS = "integrations"
    CONCURRENT_CALLS = "concurrent_calls"


class QuotaEnforcement(str, Enum):
    SOFT = "soft"
    HARD = "hard"
    NONE = "none"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


METRIC_UNITS: dict[UsageMetric, str] = {
    UsageMetric.CALL_MINUTES: "minutes",
    UsageMetric.PHONE_CALLS: "calls",
    UsageMetric.WEB_CALLS: "calls",
    UsageMetric.STT_SECONDS: "seconds",
    UsageMetric.TTS_CHARACTERS: "characters",
    UsageMetric.LLM_TOKENS: "tokens",
    UsageMetric.SMS: "messages",
    UsageMetric.WHATSAPP_INBOUND: "messages",
    UsageMetric.WHATSAPP_OUTBOUND: "messages",
    UsageMetric.MPESA_TRANSACTION: "transactions",
    UsageMetric.MPESA_COLLECTED: "KES",
    UsageMetric.STORAGE_GB: "gigabytes",
    UsageMetric.WORKFLOWS: "count",
    UsageMetric.AGENTS: "count",
    UsageMetric.USERS: "count",
    UsageMetric.INTEGRATIONS: "count",
    UsageMetric.CONCURRENT_CALLS: "count",
}

SUSPENDED_SUBSCRIPTION_STATUSES = frozenset(
    {
        SubscriptionStatus.SUSPENDED.value,
        SubscriptionStatus.CANCELLED.value,
        SubscriptionStatus.PAST_DUE.value,
    }
)


@dataclass(frozen=True)
class UsageRecordRequest:
    organization_id: int
    metric: UsageMetric
    quantity: float
    aggregation_key: str
    workflow_run_id: int | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    metadata: dict | None = None
    unit_cost: float | None = None
    billing_period: str | None = None


@dataclass
class QuotaCheckOutcome:
    allowed: bool
    metric_code: str
    used: float
    limit: float | None
    enforcement: str
    error_message: str = ""
