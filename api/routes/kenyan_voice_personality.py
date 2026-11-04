"""Kenyan voice personality selector and preview APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import KENYAN_VOICE_PERSONALITY_ENABLED
from api.db.models import UserModel
from api.schemas.kenyan_voice_personality import (
    EmotionalToneOptionSchema,
    OrgVoiceSelectionSchema,
    PreviewVoiceRequest,
    PreviewVoiceResponse,
    ToneConfigurationSchema,
    TTSChunkSchema,
    VoicePersonalityStatusSchema,
    VoiceProfileDetailSchema,
    VoiceProfileSummarySchema,
)
from api.services.auth.depends import get_user_with_selected_organization
from api.services.kenyan_voice_personality.engine import create_personality_engine
from api.services.kenyan_voice_personality.registry import get_kenyan_voice_profile_registry
from api.services.kenyan_voice_personality.resolver import get_voice_personality_resolver
from api.services.kenyan_voice_personality.schema import EmotionalTone, ToneConfiguration
from api.services.tenant import TenantContext, get_tenant_context, scoped_organization_id
from api.services.tenant.route_helpers import TenantContextDep

router = APIRouter(prefix="/kenyan-voice", tags=["kenyan-voice-personality"])

_EMOTIONAL_TONE_OPTIONS = [
    EmotionalToneOptionSchema(
        value=EmotionalTone.NEUTRAL.value,
        label="Neutral",
        description="Balanced, professional delivery",
    ),
    EmotionalToneOptionSchema(
        value=EmotionalTone.WARM.value,
        label="Warm",
        description="Friendly and welcoming",
    ),
    EmotionalToneOptionSchema(
        value=EmotionalTone.EMPATHETIC.value,
        label="Empathetic",
        description="Understanding, supportive tone",
    ),
    EmotionalToneOptionSchema(
        value=EmotionalTone.FIRM.value,
        label="Firm",
        description="Clear and authoritative",
    ),
    EmotionalToneOptionSchema(
        value=EmotionalTone.URGENT.value,
        label="Urgent",
        description="Fast-paced, action-oriented",
    ),
    EmotionalToneOptionSchema(
        value=EmotionalTone.REASSURING.value,
        label="Reassuring",
        description="Calm and confidence-building",
    ),
]


def _require_enabled() -> None:
    if not KENYAN_VOICE_PERSONALITY_ENABLED:
        raise HTTPException(status_code=503, detail="Kenyan voice personality is disabled")


def _tone_from_schema(schema: ToneConfigurationSchema | None) -> ToneConfiguration | None:
    if schema is None:
        return None
    return ToneConfiguration.from_dict(schema.model_dump())


@router.get("/status", response_model=VoicePersonalityStatusSchema)
async def voice_personality_status(
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    registry = get_kenyan_voice_profile_registry()
    return VoicePersonalityStatusSchema(
        enabled=True,
        profile_count=len(registry.list_profiles()),
        emotional_tones=_EMOTIONAL_TONE_OPTIONS,
    )


@router.get("/profiles", response_model=list[VoiceProfileSummarySchema])
async def list_voice_profiles(
    q: str = "",
    tag: str | None = None,
    domain: str | None = None,
    locale: str | None = None,
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)] = None,
):
    _require_enabled()
    registry = get_kenyan_voice_profile_registry()
    profiles = registry.search(q=q, tag=tag, domain=domain, locale=locale)
    return [
        VoiceProfileSummarySchema(
            profile_id=p.profile_id,
            style=p.style.value,
            name=p.name,
            description=p.description,
            icon=p.icon,
            domain=p.domain,
            tags=list(p.tags),
            default_tone=p.default_tone.to_dict(),
            multilingual=p.multilingual.to_dict(),
            tts_mapping=p.tts_mapping.to_dict(),
        )
        for p in profiles
    ]


@router.get("/profiles/{profile_id}", response_model=VoiceProfileDetailSchema)
async def get_voice_profile(
    profile_id: str,
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    registry = get_kenyan_voice_profile_registry()
    try:
        p = registry.require(profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Voice profile not found") from None
    data = p.to_dict()
    return VoiceProfileDetailSchema(
        profile_id=data["profile_id"],
        style=data["style"],
        name=data["name"],
        description=data["description"],
        icon=data["icon"],
        domain=data["domain"],
        tags=data["tags"],
        default_tone=data["default_tone"],
        multilingual=data["multilingual"],
        tts_mapping=data["tts_mapping"],
        playback=data["playback"],
        system_prompt_overlay=data["system_prompt_overlay"],
        search_keywords=data["search_keywords"],
    )


@router.get("/organizations/{organization_id}/selection", response_model=OrgVoiceSelectionSchema)
async def get_org_voice_selection(
    organization_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    raw = await get_voice_personality_resolver().load_org_selection(org_id)
    tone = None
    if raw.get("tone"):
        tone = ToneConfigurationSchema(**raw["tone"])
    return OrgVoiceSelectionSchema(
        organization_id=org_id,
        profile_id=raw.get("profile_id"),
        tone=tone,
    )


@router.put("/organizations/{organization_id}/selection", response_model=OrgVoiceSelectionSchema)
async def set_org_voice_selection(
    organization_id: int,
    body: OrgVoiceSelectionSchema,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    if not body.profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    tone = _tone_from_schema(body.tone)
    await get_voice_personality_resolver().save_org_selection(
        org_id, profile_id=body.profile_id, tone=tone
    )
    return OrgVoiceSelectionSchema(
        organization_id=org_id,
        profile_id=body.profile_id,
        tone=body.tone,
    )


@router.post("/preview", response_model=PreviewVoiceResponse)
async def preview_voice_personality(
    body: PreviewVoiceRequest,
    ctx: TenantContextDep,
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, body.organization_id)
    tone = _tone_from_schema(body.tone)
    try:
        engine = await create_personality_engine(
            body.profile_id,
            organization_id=org_id,
            tone=tone,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Voice profile not found") from None

    turn = engine.begin_turn(was_interrupted=body.was_interrupted)
    tts_ready, plan = engine.process_response(body.text, turn)
    normalized = engine.behavior.transform_response(body.text, turn)

    return PreviewVoiceResponse(
        normalized_text=normalized,
        tts_ready_text=tts_ready,
        chunks=[TTSChunkSchema(text=c.text, pause_after_ms=c.pause_after_ms) for c in plan.chunks],
        pause_before_ms=plan.pause_before_ms,
        speed_multiplier=plan.speed_multiplier,
        tts_mapping=engine.tts_mapping(),
        system_prompt_overlay=engine.resolved.profile.system_prompt_overlay,
    )


@router.get("/styles", response_model=list[dict])
async def list_voice_styles(
    _user: Annotated[UserModel, Depends(get_user_with_selected_organization)],
):
    _require_enabled()
    registry = get_kenyan_voice_profile_registry()
    return [
        {
            "style": p.style.value,
            "profile_id": p.profile_id,
            "name": p.name,
            "icon": p.icon,
        }
        for p in registry.list_profiles()
    ]
