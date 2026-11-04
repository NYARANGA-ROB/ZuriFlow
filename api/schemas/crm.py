"""Pydantic schemas for CRM APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DebtAccountInput(BaseModel):
    account_reference: str
    outstanding_balance: float
    currency: str = "KES"
    days_past_due: int = 0
    minimum_settlement: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateCustomerRequest(BaseModel):
    phone_e164: str
    full_name: str
    email: str | None = None
    preferred_locale: str = "mixed"
    secondary_locales: list[str] = Field(default_factory=list)
    external_crm_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    debt_account: DebtAccountInput | None = None


class UpdateCustomerRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone_e164: str | None = None
    preferred_locale: str | None = None
    secondary_locales: list[str] | None = None
    external_crm_id: str | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class UpsertDebtAccountRequest(BaseModel):
    account_reference: str
    outstanding_balance: float
    currency: str = "KES"
    days_past_due: int = 0
    minimum_settlement: float | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordPaymentRequest(BaseModel):
    amount: float
    currency: str = "KES"
    payment_method: str = "mpesa"
    status: str = "success"
    debt_account_id: int | None = None
    mpesa_transaction_id: int | None = None
    workflow_run_id: int | None = None
    receipt_reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordCallRequest(BaseModel):
    phone_e164: str
    call_type: str = "outbound"
    workflow_run_id: int | None = None
    duration_s: float | None = None
    disposition: str | None = None
    outcome: str | None = None
    summary: str | None = None
    language: str = "mixed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordEscalationRequest(BaseModel):
    reason: str
    risk_level: str = "medium"
    workflow_run_id: int | None = None
    session_id: str | None = None
    queue_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CustomerSummarySchema(BaseModel):
    id: int
    customer_uuid: str
    full_name: str
    phone_e164: str
    preferred_locale: str
    is_active: bool


class CustomerProfileSchema(BaseModel):
    id: int
    customer_uuid: str
    organization_id: int
    phone_e164: str
    full_name: str
    email: str | None
    preferred_locale: str
    secondary_locales: list[str]
    external_crm_id: str | None
    is_active: bool
    total_outstanding: float
    debt_accounts: list[dict[str, Any]]
    payment_history: list[dict[str, Any]]
    call_history: list[dict[str, Any]]
    escalation_history: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AuditLogSchema(BaseModel):
    id: int
    action: str
    resource_type: str
    resource_id: str | None
    customer_id: int | None
    actor_user_id: int | None
    changes: dict[str, Any]
    created_at: str | None
