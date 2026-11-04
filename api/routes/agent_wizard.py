"""Self-serve AI agent creation wizard API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.constants import AGENT_WIZARD_ENABLED
from api.db.models import UserModel
from api.schemas.agent_wizard import (
    IndustryOptionSchema,
    SaveBusinessHoursRequest,
    SaveCrmRequest,
    SaveEscalationRequest,
    SaveIndustryRequest,
    SaveLocaleRequest,
    SavePaymentsRequest,
    SavePersonalityRequest,
    SavePhoneRequest,
    SaveVoiceRequest,
    SaveWorkflowRequest,
    SessionResponseSchema,
    TelephonyConfigOptionSchema,
    ValidationResponseSchema,
    VoiceOptionSchema,
    WizardCatalogSchema,
    WizardStatusSchema,
)
from api.db import db_client
from api.services.agent_wizard.industries import list_industry_options
from api.services.agent_wizard.service import get_agent_wizard_service
from api.services.agent_wizard.state_machine import STEP_ORDER, WizardStep
from api.services.auth.depends import get_user_with_selected_organization

router = APIRouter(prefix="/agent-wizard", tags=["agent-wizard"])


def _require_enabled() -> None:
    if not AGENT_WIZARD_ENABLED:
        raise HTTPException(status_code=503, detail="Agent wizard is disabled")


@router.get("/status", response_model=WizardStatusSchema)
async def wizard_status(
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    return WizardStatusSchema(
        enabled=True,
        steps=[s.value for s in STEP_ORDER if s not in {WizardStep.COMPLETED, WizardStep.FAILED, WizardStep.DEPLOYING}],
    )


@router.get("/catalog", response_model=WizardCatalogSchema)
async def wizard_catalog(
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    org_id = user.selected_organization_id
    telephony: list[TelephonyConfigOptionSchema] = []
    if org_id:
        configs = await db_client.list_telephony_configurations(org_id)
        telephony = [
            TelephonyConfigOptionSchema(id=c.id, name=c.name, provider=c.provider)
            for c in configs
        ]

    voices = [
        VoiceOptionSchema(voice_id="default", label="Natural Kenyan (English & Kiswahili)"),
        VoiceOptionSchema(voice_id="warm", label="Warm and friendly"),
        VoiceOptionSchema(voice_id="professional", label="Calm and professional"),
    ]

    locales = [
        {"code": "mixed", "label": "English and Kiswahili (switch as the customer speaks)", "flag": "🇰🇪"},
        {"code": "en", "label": "English", "flag": "🇬🇧"},
        {"code": "sw", "label": "Kiswahili", "flag": "🇰🇪"},
        {"code": "sheng", "label": "Sheng-friendly (youth)", "flag": "🇰🇪"},
    ]

    personalities = [
        {"id": "friendly", "label": "Friendly neighbour"},
        {"id": "professional", "label": "Professional"},
        {"id": "casual_kenyan", "label": "Casual Kenyan"},
        {"id": "kiswahili_first", "label": "Kiswahili first"},
        {"id": "customer_care", "label": "Customer care"},
    ]

    return WizardCatalogSchema(
        industries=[IndustryOptionSchema(**item) for item in list_industry_options()],
        voices=voices,
        locales=locales,
        personalities=personalities,
        telephony_configs=telephony,
    )


@router.post("/sessions", response_model=SessionResponseSchema)
async def start_session(
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    svc = get_agent_wizard_service()
    session = await svc.start_session(user)
    payload = svc._session_payload(session)
    return SessionResponseSchema(**payload)


@router.get("/sessions/{session_uuid}", response_model=SessionResponseSchema)
async def get_session(
    session_uuid: str,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    svc = get_agent_wizard_service()
    session = await svc.get_session(session_uuid, user)
    return SessionResponseSchema(**svc._session_payload(session))


@router.delete("/sessions/{session_uuid}", status_code=204)
async def abandon_session(
    session_uuid: str,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    await get_agent_wizard_service().abandon_session(session_uuid, user)


@router.post("/sessions/{session_uuid}/industry", response_model=SessionResponseSchema)
async def save_industry(
    session_uuid: str,
    body: SaveIndustryRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.INDUSTRY, industry=body.industry
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/workflow", response_model=SessionResponseSchema)
async def save_workflow(
    session_uuid: str,
    body: SaveWorkflowRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.WORKFLOW, workflow=body.workflow
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/language", response_model=SessionResponseSchema)
async def save_language(
    session_uuid: str,
    body: SaveLocaleRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.LANGUAGE, locale=body.locale
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/payments", response_model=SessionResponseSchema)
async def save_payments(
    session_uuid: str,
    body: SavePaymentsRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.PAYMENTS, payments=body.payments
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/crm", response_model=SessionResponseSchema)
async def save_crm(
    session_uuid: str,
    body: SaveCrmRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.CRM, crm=body.crm
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/escalation", response_model=SessionResponseSchema)
async def save_escalation(
    session_uuid: str,
    body: SaveEscalationRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.ESCALATION, escalation=body.escalation
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/personality", response_model=SessionResponseSchema)
async def save_personality(
    session_uuid: str,
    body: SavePersonalityRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid,
        user,
        step=WizardStep.VOICE,
        personality=body.personality,
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/voice", response_model=SessionResponseSchema)
async def save_voice(
    session_uuid: str,
    body: SaveVoiceRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid,
        user,
        step=WizardStep.VOICE,
        voice=body.voice,
        personality=body.personality,
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/business-hours", response_model=SessionResponseSchema)
async def save_business_hours(
    session_uuid: str,
    body: SaveBusinessHoursRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid,
        user,
        step=WizardStep.BUSINESS_HOURS,
        business_hours=body.business_hours,
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/phone", response_model=SessionResponseSchema)
async def save_phone(
    session_uuid: str,
    body: SavePhoneRequest,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().save_step(
        session_uuid, user, step=WizardStep.PHONE, phone=body.phone
    )
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/advance", response_model=SessionResponseSchema)
async def advance_session(
    session_uuid: str,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().advance(session_uuid, user)
    return SessionResponseSchema(**payload)


@router.post("/sessions/{session_uuid}/back", response_model=SessionResponseSchema)
async def go_back(
    session_uuid: str,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().go_back(session_uuid, user)
    return SessionResponseSchema(**payload)


@router.get("/sessions/{session_uuid}/validate", response_model=ValidationResponseSchema)
async def validate_session(
    session_uuid: str,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    result = await get_agent_wizard_service().validate_current(session_uuid, user)
    return ValidationResponseSchema(**result)


@router.post("/sessions/{session_uuid}/deploy", response_model=SessionResponseSchema)
async def deploy_agent(
    session_uuid: str,
    user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    payload = await get_agent_wizard_service().deploy(session_uuid, user)
    return SessionResponseSchema(**payload)
