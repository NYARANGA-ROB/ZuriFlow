"""Billing configuration and API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from api.services.tenant_billing.types import InvoiceStatus, SubscriptionStatus, UsageMetric


class TenantUsageRates(BaseModel):
    """Unit prices come from the configured plan catalog or org settings. Defaults are zero."""

    per_minute_usd: float = Field(default=0.0, ge=0)
    per_phone_call_usd: float = Field(default=0.0, ge=0)
    per_web_call_usd: float = Field(default=0.0, ge=0)
    stt_per_minute_usd: float = Field(default=0.0, ge=0)
    tts_per_1k_chars_usd: float = Field(default=0.0, ge=0)
    llm_per_1k_tokens_usd: float = Field(default=0.0, ge=0)
    sms_per_message_usd: float = Field(default=0.0, ge=0)
    whatsapp_per_message_usd: float = Field(default=0.0, ge=0)
    mpesa_per_transaction_usd: float = Field(default=0.0, ge=0)
    storage_per_gb_usd: float = Field(default=0.0, ge=0)


class TenantQuotaConfig(BaseModel):
    call_minutes_monthly: Optional[float] = Field(default=None, ge=0)
    stt_minutes_monthly: Optional[float] = Field(default=None, ge=0)
    whatsapp_messages_monthly: Optional[float] = Field(default=None, ge=0)
    concurrent_calls: Optional[float] = Field(default=None, ge=0)
    agents: Optional[float] = Field(default=None, ge=0)
    workflows: Optional[float] = Field(default=None, ge=0)
    users: Optional[float] = Field(default=None, ge=0)
    storage_gb: Optional[float] = Field(default=None, ge=0)
    integrations: Optional[float] = Field(default=None, ge=0)


class TenantSubscriptionConfig(BaseModel):
    status: SubscriptionStatus = SubscriptionStatus.TRIALING
    tier: str = "starter"
    trial_ends_at: Optional[str] = None


class TenantBillingPlanSchema(BaseModel):
    plan_id: str = "starter"
    currency: str = "KES"
    rates: TenantUsageRates = Field(default_factory=TenantUsageRates)
    quotas: TenantQuotaConfig = Field(default_factory=TenantQuotaConfig)
    subscription: TenantSubscriptionConfig = Field(
        default_factory=TenantSubscriptionConfig
    )


class UsageEventSchema(BaseModel):
    id: int
    organization_id: int
    metric_code: str
    quantity: float
    unit: str
    billable_amount: Optional[float] = None
    unit_cost: Optional[float] = None
    billing_period: Optional[str] = None
    currency: str
    workflow_run_id: Optional[int] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    recorded_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UsageSummarySchema(BaseModel):
    organization_id: int
    from_ts: str
    to_ts: str
    metrics: Dict[str, Dict[str, Any]]
    total_billable_amount: float
    currency: str


class QuotaSchema(BaseModel):
    metric_code: str
    period: str
    limit_quantity: float
    used_quantity: float
    remaining_quantity: Optional[float] = None
    enforcement: str
    exceeded: bool = False


class UpsertQuotaRequest(BaseModel):
    metric_code: UsageMetric
    limit_quantity: float = Field(gt=0)
    period: Literal["monthly", "annual"] = "monthly"
    enforcement: Literal["soft", "hard", "none"] = "soft"


class InvoiceLineSchema(BaseModel):
    metric_code: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    amount: float


class InvoiceSchema(BaseModel):
    id: int
    organization_id: int
    invoice_number: str
    period_start: str
    period_end: str
    status: InvoiceStatus
    currency: str
    subtotal: float
    tax_amount: float
    total_amount: float
    issued_at: Optional[str] = None
    line_items: List[InvoiceLineSchema] = Field(default_factory=list)


class GenerateInvoiceRequest(BaseModel):
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    issue: bool = False


class UpdateSubscriptionRequest(BaseModel):
    status: SubscriptionStatus
    tier: Optional[str] = None
