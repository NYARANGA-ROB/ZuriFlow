from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class STKPushRequestSchema(BaseModel):
    phone_e164: str
    amount: float = Field(gt=0)
    account_reference: str = Field(max_length=12)
    transaction_desc: str = Field(max_length=13, default="Payment")
    workflow_run_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class STKPushResponseSchema(BaseModel):
    success: bool
    transaction_id: int | None = None
    merchant_request_id: str | None = None
    checkout_request_id: str | None = None
    customer_message: str | None = None
    error: str | None = None


class MpesaTransactionEventSchema(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime | None = None


class MpesaTransactionSchema(BaseModel):
    id: int
    organization_id: int
    workflow_run_id: int | None = None
    phone_e164: str
    amount: float
    currency: str
    account_reference: str
    transaction_desc: str
    merchant_request_id: str | None = None
    checkout_request_id: str | None = None
    mpesa_receipt_number: str | None = None
    status: str
    result_code: int | None = None
    result_desc: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    events: list[MpesaTransactionEventSchema] = Field(default_factory=list)


class MpesaCallbackResponse(BaseModel):
    ResultCode: int = 0
    ResultDesc: str = "Accepted"
