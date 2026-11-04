"""Types for Kenyan debt collection workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class CommitmentStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    PARTIAL = "partial"
    BROKEN = "broken"
    FULFILLED = "fulfilled"


class NegotiationOutcome(str, Enum):
    FULL_PAYMENT = "full_payment"
    INSTALLMENT_PLAN = "installment_plan"
    PARTIAL_COMMITMENT = "partial_commitment"
    REFUSED = "refused"
    ESCALATED = "escalated"
    PENDING = "pending"


class EscalationRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DebtAccount:
    account_id: str
    customer_name: str
    phone_e164: str
    outstanding_balance: float
    currency: str = "KES"
    days_past_due: int = 0
    minimum_settlement: float | None = None

    @property
    def settlement_floor(self) -> float:
        if self.minimum_settlement is not None:
            return self.minimum_settlement
        return round(self.outstanding_balance * 0.6, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "customer_name": self.customer_name,
            "phone_e164": self.phone_e164,
            "outstanding_balance": self.outstanding_balance,
            "currency": self.currency,
            "days_past_due": self.days_past_due,
            "minimum_settlement": self.minimum_settlement,
        }


@dataclass
class PaymentCommitment:
    commitment_id: str
    amount: float
    due_date: date
    status: CommitmentStatus = CommitmentStatus.PROPOSED
    installment_index: int = 0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "amount": self.amount,
            "due_date": self.due_date.isoformat(),
            "status": self.status.value,
            "installment_index": self.installment_index,
            "notes": self.notes,
        }


@dataclass
class InstallmentPlan:
    plan_id: str
    total_amount: float
    installments: tuple[PaymentCommitment, ...]
    frequency: str = "monthly"
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "total_amount": self.total_amount,
            "installments": [c.to_dict() for c in self.installments],
            "frequency": self.frequency,
            "approved": self.approved,
        }


@dataclass
class NegotiationOffer:
    offered_amount: float
    term_months: int = 1
    upfront_amount: float = 0.0
    message_key: str = "standard_offer"
    acceptable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "offered_amount": self.offered_amount,
            "term_months": self.term_months,
            "upfront_amount": self.upfront_amount,
            "message_key": self.message_key,
            "acceptable": self.acceptable,
        }


@dataclass
class DebtCollectionSession:
    session_id: str
    organization_id: int
    workflow_run_id: int | None = None
    vertical_instance_id: str = ""
    account: DebtAccount | None = None
    locale: str = "mixed"
    negotiation_rounds: int = 0
    refusal_count: int = 0
    interruption_count: int = 0
    frustration_score: float = 0.0
    escalation_risk: EscalationRisk = EscalationRisk.LOW
    current_offer: NegotiationOffer | None = None
    installment_plan: InstallmentPlan | None = None
    commitments: list[PaymentCommitment] = field(default_factory=list)
    outcome: NegotiationOutcome = NegotiationOutcome.PENDING
    variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "vertical_instance_id": self.vertical_instance_id,
            "account": self.account.to_dict() if self.account else None,
            "locale": self.locale,
            "negotiation_rounds": self.negotiation_rounds,
            "refusal_count": self.refusal_count,
            "interruption_count": self.interruption_count,
            "frustration_score": self.frustration_score,
            "escalation_risk": self.escalation_risk.value,
            "current_offer": self.current_offer.to_dict() if self.current_offer else None,
            "installment_plan": self.installment_plan.to_dict() if self.installment_plan else None,
            "commitments": [c.to_dict() for c in self.commitments],
            "outcome": self.outcome.value,
            "variables": dict(self.variables),
        }
