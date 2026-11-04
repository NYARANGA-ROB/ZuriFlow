"""API schemas for the self-serve agent creation wizard."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.services.agent_wizard.schema import (
    BusinessHoursConfig,
    CrmConfig,
    EscalationConfig,
    IndustrySelection,
    LocaleConfig,
    PaymentsConfig,
    PersonalityConfig,
    PhoneConfig,
    VoiceConfig,
    WorkflowSelection,
)


class WizardStatusSchema(BaseModel):
    enabled: bool
    estimated_minutes: int = 10
    steps: list[str]


class IndustryOptionSchema(BaseModel):
    industry_id: str
    name: str
    description: str
    icon: str
    recommended_template_id: str | None
    template_name: str | None
    supported_locales: list[str]
    supports_mpesa: bool
    default_locale: str
    example_use_cases: list[str]
    business_type: str = ""


class VoiceOptionSchema(BaseModel):
    voice_id: str
    label: str
    provider: str = "dograh"
    language: str = "multi"


class TelephonyConfigOptionSchema(BaseModel):
    id: int
    name: str
    provider: str


class SessionResponseSchema(BaseModel):
    session_uuid: str
    organization_id: int
    state: str
    progress_percent: int
    config: dict[str, Any]
    workflow_id: int | None
    phone_number_id: int | None
    error_message: str | None
    completed_at: str | None
    created_at: str | None
    updated_at: str | None
    deployment: dict[str, Any] | None = None


class SaveIndustryRequest(BaseModel):
    industry: IndustrySelection


class SaveWorkflowRequest(BaseModel):
    workflow: WorkflowSelection


class SaveLocaleRequest(BaseModel):
    locale: LocaleConfig


class SaveVoiceRequest(BaseModel):
    voice: VoiceConfig
    personality: PersonalityConfig | None = None


class SaveBusinessHoursRequest(BaseModel):
    business_hours: BusinessHoursConfig


class SavePhoneRequest(BaseModel):
    phone: PhoneConfig


class SavePaymentsRequest(BaseModel):
    payments: PaymentsConfig


class SaveCrmRequest(BaseModel):
    crm: CrmConfig


class SaveEscalationRequest(BaseModel):
    escalation: EscalationConfig


class SavePersonalityRequest(BaseModel):
    personality: PersonalityConfig


class ValidationResponseSchema(BaseModel):
    valid: bool
    errors: list[str]
    step: str


class WizardCatalogSchema(BaseModel):
    industries: list[IndustryOptionSchema]
    voices: list[VoiceOptionSchema]
    locales: list[dict[str, str]]
    personalities: list[dict[str, str]] = Field(default_factory=list)
    telephony_configs: list[TelephonyConfigOptionSchema] = Field(default_factory=list)
