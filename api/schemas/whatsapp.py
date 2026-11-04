from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SendCallSummaryRequest(BaseModel):
    phone_e164: str
    customer_name: str = "there"
    summary: str
    intent: str = ""
    next_steps: str = ""
    workflow_run_id: int | None = None
    provider: str | None = None


class SendPaymentLinkRequest(BaseModel):
    phone_e164: str
    customer_name: str
    amount: str
    payment_url: str
    reference: str = ""
    workflow_run_id: int | None = None
    provider: str | None = None


class SendAppointmentRequest(BaseModel):
    phone_e164: str
    customer_name: str
    appointment_date: str
    appointment_time: str
    location: str = ""
    workflow_run_id: int | None = None
    provider: str | None = None


class EscalateConversationRequest(BaseModel):
    reason: str
    context: str = ""
    customer_phone: str | None = None


class WhatsAppMessageResponse(BaseModel):
    id: int
    direction: str
    body: str
    template_name: str | None = None
    status: str
    provider_message_id: str | None = None
    created_at: datetime | None = None


class WhatsAppConversationResponse(BaseModel):
    id: int
    phone_e164: str
    provider: str
    workflow_run_id: int | None = None
    status: str
    escalated: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    messages: list[WhatsAppMessageResponse] = Field(default_factory=list)


class SendMessageResult(BaseModel):
    success: bool
    conversation_id: int | None = None
    message_id: int | None = None
    provider_message_id: str | None = None
    error: str | None = None


class PostCallSummaryRequest(BaseModel):
    phone_e164: str
    workflow_run_id: int
    customer_name: str = "there"
    memory_snapshot: dict[str, Any] | None = None
    gathered_context: dict[str, Any] | None = None
