"""Guided organization setup for Kenyan SMEs and enterprises."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.db import db_client
from api.enums import OrganizationConfigurationKey
from api.services.control_plane.audit import PAYMENT_SETTINGS_CHANGED, log_admin_action

KENYA_COUNTIES = [
    "Baringo",
    "Bomet",
    "Bungoma",
    "Busia",
    "Elgeyo-Marakwet",
    "Embu",
    "Garissa",
    "Homa Bay",
    "Isiolo",
    "Kajiado",
    "Kakamega",
    "Kericho",
    "Kiambu",
    "Kilifi",
    "Kirinyaga",
    "Kisii",
    "Kisumu",
    "Kitui",
    "Kwale",
    "Laikipia",
    "Lamu",
    "Machakos",
    "Makueni",
    "Mandera",
    "Marsabit",
    "Meru",
    "Migori",
    "Mombasa",
    "Murang'a",
    "Nairobi",
    "Nakuru",
    "Nandi",
    "Narok",
    "Nyamira",
    "Nyandarua",
    "Nyeri",
    "Samburu",
    "Siaya",
    "Taita-Taveta",
    "Tana River",
    "Tharaka-Nithi",
    "Trans Nzoia",
    "Turkana",
    "Uasin Gishu",
    "Vihiga",
    "Wajir",
    "West Pokot",
]

INDUSTRIES = [
    "retail",
    "hospitality",
    "healthcare",
    "education",
    "finance",
    "logistics",
    "agriculture",
    "utilities",
    "government",
    "professional_services",
    "other",
]


class BusinessHours(BaseModel):
    timezone: str = "Africa/Nairobi"
    weekdays: str = "08:00-17:00"
    saturday: str | None = "09:00-13:00"
    sunday: str | None = None


class PhoneNumberEntry(BaseModel):
    label: str = "main"
    number: str
    purpose: str = "inbound"


class PaymentConfiguration(BaseModel):
    mpesa_enabled: bool = True
    paybill: str | None = None
    till_number: str | None = None
    account_reference: str | None = None


class EscalationContact(BaseModel):
    name: str
    phone: str
    role: str = "supervisor"


class CommunicationChannels(BaseModel):
    voice: bool = True
    sms: bool = True
    whatsapp: bool = True
    email: bool = False


class OrganizationSetupProfile(BaseModel):
    business_name: str | None = None
    industry: str | None = None
    location: str | None = None
    county: str | None = None
    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    phone_numbers: list[PhoneNumberEntry] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["en", "sw"])
    payment: PaymentConfiguration = Field(default_factory=PaymentConfiguration)
    escalation_contacts: list[EscalationContact] = Field(default_factory=list)
    channels: CommunicationChannels = Field(default_factory=CommunicationChannels)

    def completeness(self) -> dict[str, Any]:
        checks = {
            "business_name": bool(self.business_name),
            "industry": bool(self.industry),
            "location": bool(self.location),
            "county": bool(self.county),
            "business_hours": bool(self.business_hours.weekdays),
            "phone_numbers": bool(self.phone_numbers),
            "languages": bool(self.languages),
            "payment": bool(
                self.payment.paybill or self.payment.till_number or not self.payment.mpesa_enabled
            ),
            "escalation_contacts": bool(self.escalation_contacts),
            "channels": True,
        }
        done = sum(1 for v in checks.values() if v)
        return {
            "steps": checks,
            "completed": done,
            "total": len(checks),
            "ready": done == len(checks),
        }


async def get_setup_profile(organization_id: int) -> OrganizationSetupProfile:
    row = await db_client.get_configuration(
        organization_id, OrganizationConfigurationKey.CONTROL_PLANE_PROFILE.value
    )
    if not row or not isinstance(row.value, dict):
        return OrganizationSetupProfile()
    return OrganizationSetupProfile.model_validate(row.value)


async def save_setup_profile(
    organization_id: int,
    profile: OrganizationSetupProfile,
    *,
    actor_user_id: int | None = None,
) -> OrganizationSetupProfile:
    previous = await get_setup_profile(organization_id)
    await db_client.upsert_configuration(
        organization_id,
        OrganizationConfigurationKey.CONTROL_PLANE_PROFILE.value,
        profile.model_dump(mode="json"),
    )
    if previous.payment.model_dump() != profile.payment.model_dump():
        await log_admin_action(
            organization_id=organization_id,
            action=PAYMENT_SETTINGS_CHANGED,
            resource_type="payment_settings",
            actor_user_id=actor_user_id,
            summary="Payment configuration updated",
        )
    if profile.completeness().get("ready"):
        from api.services.product_analytics import track_once

        await track_once(
            organization_id,
            "activation",
            properties={"source": "organization_setup"},
        )
    from api.services.business_twin.service import save_profile

    await save_profile(
        organization_id,
        {
            "legal_name": profile.business_name,
            "industry": profile.industry,
            "counties": [profile.county] if profile.county else [],
            "languages": profile.languages,
            "hours": profile.business_hours.model_dump(),
            "payment": profile.payment.model_dump(),
            "phones": [p.number for p in profile.phone_numbers],
        },
        actor_user_id=actor_user_id,
        source="business_admin",
    )
    return profile
