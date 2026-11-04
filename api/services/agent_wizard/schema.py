"""Configuration schema for self-serve agent setup."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from api.services.kenya.config import KENYA

CallDirection = Literal["inbound", "outbound"]
TemplateSource = Literal["vertical", "workflow_db", "generated"]
PrimaryLocale = Literal["en", "sw", "mixed", "fr", "sheng"]


class DaySchedule(BaseModel):
    """Business hours for a single weekday."""

    enabled: bool = True
    open_time: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    close_time: str = Field(default="17:00", pattern=r"^\d{2}:\d{2}$")


class BusinessHoursConfig(BaseModel):
    timezone: str = KENYA.timezone
    schedule: dict[str, DaySchedule] = Field(default_factory=dict)
    after_hours_message_en: str = (
        "Thank you for calling. Our office is currently closed. "
        "Please call back during business hours."
    )
    after_hours_message_sw: str = (
        "Asante kwa kupiga simu. Ofisi yetu imefungwa kwa sasa. "
        "Tafadhali piga tena wakati wa kazi."
    )

    @model_validator(mode="after")
    def _default_week(self) -> "BusinessHoursConfig":
        if not self.schedule:
            weekday = DaySchedule()
            self.schedule = {
                day: weekday.model_copy()
                for day in (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
            }
            self.schedule["saturday"] = DaySchedule(enabled=False)
            self.schedule["sunday"] = DaySchedule(enabled=False)
        return self


class LocaleConfig(BaseModel):
    primary_locale: PrimaryLocale = "mixed"
    secondary_locales: list[PrimaryLocale] = Field(default_factory=list)
    kenyan_language_mode: Literal["english", "swahili", "mixed", "sheng"] = "mixed"


class PaymentsConfig(BaseModel):
    enable_mpesa: bool = False
    enable_sms: bool = True
    enable_whatsapp: bool = True
    currency: str = "KES"


class CrmConfig(BaseModel):
    enable_crm: bool = True
    enable_timeline: bool = True
    enable_analytics: bool = True


class EscalationConfig(BaseModel):
    enable_human_escalation: bool = True
    after_hours_escalate: bool = True
    notes: str = ""


class PersonalityConfig(BaseModel):
    style: str = "friendly"


class VoiceConfig(BaseModel):
    provider: str = "dograh"
    voice_id: str = "default"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    language: str = "multi"


class PhoneConfig(BaseModel):
    telephony_configuration_id: int | None = None
    address: str | None = None
    country_code: str = "KE"
    label: str | None = None
    skip_assignment: bool = False


class IndustrySelection(BaseModel):
    industry_id: str
    template_id: str | None = None
    template_source: TemplateSource = "vertical"


class WorkflowSelection(BaseModel):
    agent_name: str = Field(min_length=2, max_length=120)
    call_direction: CallDirection = "inbound"
    use_case: str = Field(default="", max_length=200)
    activity_description: str = Field(default="", max_length=2000)


class AgentWizardConfig(BaseModel):
    """Full wizard payload persisted on the setup session."""

    industry: IndustrySelection | None = None
    workflow: WorkflowSelection | None = None
    locale: LocaleConfig | None = None
    payments: PaymentsConfig | None = None
    crm: CrmConfig | None = None
    escalation: EscalationConfig | None = None
    voice: VoiceConfig | None = None
    personality: PersonalityConfig | None = None
    business_hours: BusinessHoursConfig | None = None
    phone: PhoneConfig | None = None
    website_url: str | None = None
    knowledge_ready: bool = False
    integrations_ready: bool = False
    discovered_reviewed: bool = False
    test_completed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_storage(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_storage(cls, data: dict[str, Any] | None) -> "AgentWizardConfig":
        if not data:
            return cls()
        return cls.model_validate(data)
