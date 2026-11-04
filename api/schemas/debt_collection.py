"""Pydantic schemas for debt collection APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DebtAccountSchema(BaseModel):
    account_id: str
    customer_name: str
    phone_e164: str
    outstanding_balance: float
    currency: str = "KES"
    days_past_due: int = 0
    minimum_settlement: float | None = None


class StartDebtCollectionRequest(BaseModel):
    organization_id: int
    account: DebtAccountSchema
    workflow_run_id: int | None = None
    locale: str = "mixed"
    session_id: str | None = None


class TranscriptRequest(BaseModel):
    text: str
    is_final: bool = True
    interrupted: bool = False


class NegotiateRequest(BaseModel):
    customer_offer_amount: float | None = None
    accept: bool = False


class PaymentStatusRequest(BaseModel):
    status: str
    amount: float | None = None
    receipt: str = ""


class DebtCollectionResponse(BaseModel):
    session_id: str
    vertical_instance_id: str
    prompt: str
    locale: str
    current_step_id: str = ""
    negotiation_outcome: str = "pending"
    escalation_risk: str = "low"
    commitments: list[dict[str, Any]] = Field(default_factory=list)
    installment_plan: dict[str, Any] | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None
    actions_taken: list[dict[str, Any]] = Field(default_factory=list)
    escalated: bool = False
    payment_requested: bool = False
    interruption_ack: str | None = None
    compliance: dict[str, Any] | None = None


class ComplianceCheckRequest(BaseModel):
    text: str
    speaker: str = "agent"


class ComplianceAuditSchema(BaseModel):
    session_id: str
    entries: list[dict[str, Any]]
    violation_count: int = 0


class SessionDetailSchema(BaseModel):
    session_id: str
    organization_id: int
    workflow_run_id: int | None
    vertical_instance_id: str
    locale: str
    negotiation_outcome: str
    escalation_risk: str
    negotiation_rounds: int
    refusal_count: int
    interruption_count: int
    commitments: list[dict[str, Any]]
    installment_plan: dict[str, Any] | None
    account: dict[str, Any] | None
