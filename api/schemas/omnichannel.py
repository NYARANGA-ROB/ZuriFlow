"""API schemas for unified omnichannel engagement."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResolveIdentityRequest(BaseModel):
    phone: str | None = None
    email: str | None = None
    whatsapp_id: str | None = None
    crm_id: str | None = None
    customer_id: int | None = None
    full_name: str | None = None
    preferred_locale: str = "mixed"


class OrchestrateRequest(BaseModel):
    action: str
    phone: str | None = None
    email: str | None = None
    whatsapp_id: str | None = None
    crm_id: str | None = None
    customer_id: int | None = None
    body: str | None = None
    purpose: str = "transactional"
    channel: str | None = None
    workflow_run_id: int | None = None
    transaction_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InboundMessageRequest(BaseModel):
    channel: str
    body: str
    phone: str | None = None
    email: str | None = None
    whatsapp_id: str | None = None
    customer_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FollowupRequest(BaseModel):
    trigger: str
    phone: str | None = None
    customer_id: int | None = None
    body: str | None = None
    transaction_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreferencesUpdateRequest(BaseModel):
    customer_id: int
    preferred_channel: str | None = None
    preferred_locale: str | None = None
    marketing_consent: bool | None = None
    transactional_consent: bool | None = None
    sms_opt_out: bool | None = None
    whatsapp_opt_out: bool | None = None
    voice_opt_out: bool | None = None
    email_opt_out: bool | None = None
    webchat_opt_out: bool | None = None
    consent_source: str | None = None
    notes: str | None = None
