"""Unified omnichannel customer engagement APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import OMNICHANNEL_ENABLED
from api.db.models import UserModel
from api.schemas.omnichannel import (
    FollowupRequest,
    InboundMessageRequest,
    OrchestrateRequest,
    PreferencesUpdateRequest,
    ResolveIdentityRequest,
)
from api.services.auth.depends import get_user
from api.services.omnichannel import get_omnichannel_service
from api.services.tenant import get_tenant_context
from api.services.tenant.types import TenantContext

router = APIRouter(prefix="/omnichannel", tags=["omnichannel"])


def _require_enabled() -> None:
    if not OMNICHANNEL_ENABLED:
        raise HTTPException(status_code=503, detail="Omnichannel engagement is disabled")


@router.get("/status")
async def omnichannel_status(_user: UserModel = Depends(get_user)):
    return {"enabled": get_omnichannel_service().enabled}


@router.post("/identity/resolve")
async def resolve_identity(
    body: ResolveIdentityRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    match = await get_omnichannel_service().resolve_identity(
        organization_id=ctx.organization_id,
        **body.model_dump(),
    )
    return match.to_dict()


@router.post("/orchestrate")
async def orchestrate(
    body: OrchestrateRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    return await get_omnichannel_service().orchestrate(
        organization_id=ctx.organization_id,
        **body.model_dump(),
    )


@router.post("/inbound")
async def ingest_inbound(
    body: InboundMessageRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    return await get_omnichannel_service().ingest_inbound(
        organization_id=ctx.organization_id,
        **body.model_dump(),
    )


@router.post("/followups")
async def run_followup(
    body: FollowupRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    return {
        "results": await get_omnichannel_service().handle_followup(
            organization_id=ctx.organization_id,
            **body.model_dump(),
        )
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    return await get_omnichannel_service().conversation_timeline(
        organization_id=ctx.organization_id,
        conversation_id=conversation_id,
    )


@router.put("/preferences")
async def update_preferences(
    body: PreferencesUpdateRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    data = body.model_dump(exclude_none=True)
    customer_id = data.pop("customer_id")
    prefs = await get_omnichannel_service().update_preferences(
        organization_id=ctx.organization_id,
        customer_id=customer_id,
        **data,
    )
    return {
        "customer_id": customer_id,
        "preferred_channel": prefs.preferred_channel,
        "preferred_locale": prefs.preferred_locale,
        "marketing_consent": prefs.marketing_consent,
        "transactional_consent": prefs.transactional_consent,
        "sms_opt_out": prefs.sms_opt_out,
        "whatsapp_opt_out": prefs.whatsapp_opt_out,
        "voice_opt_out": prefs.voice_opt_out,
        "legal_basis": prefs.legal_basis,
    }


@router.get("/dashboard")
async def engagement_dashboard(
    days: int = Query(30, ge=1, le=90),
    ctx: TenantContext = Depends(get_tenant_context),
    _user: UserModel = Depends(get_user),
):
    _require_enabled()
    return await get_omnichannel_service().dashboard(
        organization_id=ctx.organization_id,
        days=days,
    )
