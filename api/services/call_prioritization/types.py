"""Domain types for predictive call prioritization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CallOutcome(str, Enum):
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    VOICEMAIL = "voicemail"
    PAYMENT_COLLECTED = "payment_collected"
    NEGOTIATION = "negotiation"
    ESCALATED = "escalated"


ANSWERED_OUTCOMES = frozenset(
    {
        CallOutcome.ANSWERED.value,
        "debt_collection_started",
        CallOutcome.NEGOTIATION.value,
        CallOutcome.PAYMENT_COLLECTED.value,
        "payment_commitment",
        "installment_scheduled",
    }
)

FAILED_OUTCOMES = frozenset(
    {
        CallOutcome.NO_ANSWER.value,
        CallOutcome.BUSY.value,
        CallOutcome.FAILED.value,
        CallOutcome.VOICEMAIL.value,
        "disconnected",
    }
)


@dataclass
class PrioritizationSignals:
    """Raw CRM-derived features for scoring."""

    customer_id: int
    organization_id: int
    phone_e164: str
    full_name: str
    preferred_locale: str = "mixed"
    total_outstanding: float = 0.0
    days_past_due: int = 0
    successful_payments: int = 0
    total_paid: float = 0.0
    days_since_last_payment: int | None = None
    total_calls: int = 0
    answered_calls: int = 0
    failed_calls: int = 0
    days_since_last_answer: int | None = None
    positive_conversations: int = 0
    total_escalations: int = 0
    unresolved_escalations: int = 0
    high_risk_escalations: int = 0
    consecutive_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "organization_id": self.organization_id,
            "phone_e164": self.phone_e164,
            "full_name": self.full_name,
            "preferred_locale": self.preferred_locale,
            "total_outstanding": self.total_outstanding,
            "days_past_due": self.days_past_due,
            "successful_payments": self.successful_payments,
            "total_paid": self.total_paid,
            "days_since_last_payment": self.days_since_last_payment,
            "total_calls": self.total_calls,
            "answered_calls": self.answered_calls,
            "failed_calls": self.failed_calls,
            "days_since_last_answer": self.days_since_last_answer,
            "positive_conversations": self.positive_conversations,
            "total_escalations": self.total_escalations,
            "unresolved_escalations": self.unresolved_escalations,
            "high_risk_escalations": self.high_risk_escalations,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class ScoreBreakdown:
    payment_score: float = 0.0
    answer_rate_score: float = 0.0
    engagement_score: float = 0.0
    escalation_penalty: float = 0.0
    failure_penalty: float = 0.0
    recency_bonus: float = 0.0

    @property
    def total(self) -> float:
        return max(
            0.0,
            min(
                100.0,
                self.payment_score
                + self.answer_rate_score
                + self.engagement_score
                + self.recency_bonus
                - self.escalation_penalty
                - self.failure_penalty,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "payment_score": round(self.payment_score, 2),
            "answer_rate_score": round(self.answer_rate_score, 2),
            "engagement_score": round(self.engagement_score, 2),
            "escalation_penalty": round(self.escalation_penalty, 2),
            "failure_penalty": round(self.failure_penalty, 2),
            "recency_bonus": round(self.recency_bonus, 2),
            "total": round(self.total, 2),
        }


@dataclass
class PrioritizationScore:
    customer_id: int
    organization_id: int
    score: float
    tier: str
    breakdown: ScoreBreakdown
    signals: PrioritizationSignals
    likely_payer: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "organization_id": self.organization_id,
            "score": round(self.score, 2),
            "tier": self.tier,
            "likely_payer": self.likely_payer,
            "breakdown": self.breakdown.to_dict(),
            "signals": self.signals.to_dict(),
        }


@dataclass
class PrioritizedCallEntry:
    customer_id: int
    organization_id: int
    phone_e164: str
    full_name: str
    score: float
    tier: str
    preferred_locale: str = "mixed"
    workflow_run_id: int | None = None
    debt_account_reference: str | None = None
    outstanding_balance: float | None = None
    attempt_number: int = 1
    enqueued_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "organization_id": self.organization_id,
            "phone_e164": self.phone_e164,
            "full_name": self.full_name,
            "score": round(self.score, 2),
            "tier": self.tier,
            "preferred_locale": self.preferred_locale,
            "workflow_run_id": self.workflow_run_id,
            "debt_account_reference": self.debt_account_reference,
            "outstanding_balance": self.outstanding_balance,
            "attempt_number": self.attempt_number,
            "enqueued_at": self.enqueued_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrioritizedCallEntry:
        return cls(
            customer_id=int(data["customer_id"]),
            organization_id=int(data["organization_id"]),
            phone_e164=str(data["phone_e164"]),
            full_name=str(data.get("full_name", "")),
            score=float(data["score"]),
            tier=str(data.get("tier", "medium")),
            preferred_locale=str(data.get("preferred_locale", "mixed")),
            workflow_run_id=data.get("workflow_run_id"),
            debt_account_reference=data.get("debt_account_reference"),
            outstanding_balance=data.get("outstanding_balance"),
            attempt_number=int(data.get("attempt_number", 1)),
            enqueued_at=float(data.get("enqueued_at", 0.0)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class RetrySchedule:
    customer_id: int
    organization_id: int
    scheduled_at: float
    attempt_number: int
    reason: str
    score: float
    delay_s: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "organization_id": self.organization_id,
            "scheduled_at": self.scheduled_at,
            "attempt_number": self.attempt_number,
            "reason": self.reason,
            "score": round(self.score, 2),
            "delay_s": self.delay_s,
        }
