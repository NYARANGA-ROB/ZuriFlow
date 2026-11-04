"""Voice campaign management API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db import db_client
from api.db.models import UserModel
from api.schemas.voice_campaign import (
    CampaignAnalyticsSchema,
    ConfigureCampaignRequest,
    CreateCrmCampaignRequest,
    ScheduleRetryRequest,
)
from api.services.auth.depends import get_user
from api.services.tenant import assert_campaign_belongs_to_tenant, get_tenant_context
from api.services.tenant.route_helpers import TenantContextDep
from api.services.tenant.types import TenantContext
from api.services.voice_campaign.service import get_voice_campaign_service

router = APIRouter(prefix="/voice-campaign", tags=["voice-campaign"])


async def get_organization_id(
    ctx: TenantContext = Depends(get_tenant_context),
) -> int:
    return ctx.organization_id


@router.get("/status")
async def voice_campaign_status(_user=Depends(get_user)):
    svc = get_voice_campaign_service()
    return {"enabled": svc.enabled}


@router.post("/campaigns/crm")
async def create_crm_campaign(
    body: CreateCrmCampaignRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_voice_campaign_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Voice campaign engine is disabled")

    campaign = await db_client.create_campaign(
        name=body.name,
        workflow_id=body.workflow_id,
        source_type="crm",
        source_id=json.dumps(body.segment),
        user_id=user.id,
        organization_id=organization_id,
        retry_config=body.retry_config,
        max_concurrency=body.max_concurrency,
        schedule_config=body.schedule_config,
        telephony_configuration_id=body.telephony_configuration_id,
    )
    meta = dict(campaign.orchestrator_metadata or {})
    meta["voice_campaign_enabled"] = True
    meta["locale_config"] = body.segment.get("locale_config") or {
        "default_locale": body.segment.get("default_locale", "mixed"),
    }
    meta["throttle"] = {"use_priority_queue": body.segment.get("use_priority", True)}
    await db_client.update_campaign(
        campaign_id=campaign.id,
        rate_limit_per_second=body.rate_limit_per_second,
        orchestrator_metadata=meta,
    )
    return {"campaign_id": campaign.id, "source_type": "crm"}


@router.patch("/campaigns/{campaign_id}/configure")
async def configure_campaign(
    campaign_id: int,
    body: ConfigureCampaignRequest,
    ctx: TenantContextDep,
):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    try:
        return await svc.configure_campaign(
            campaign_id,
            scheduled_start_at=body.scheduled_start_at,
            locale_config=body.locale_config,
            throttle=body.throttle,
            contact_timezone_field=body.contact_timezone_field,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/campaigns/{campaign_id}/start")
async def start_managed_campaign(campaign_id: int, ctx: TenantContextDep):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    try:
        await svc.start_campaign(campaign_id)
        return {"started": True, "campaign_id": campaign_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/campaigns/{campaign_id}/throttle")
async def get_throttle_plan(campaign_id: int, ctx: TenantContextDep):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    try:
        return await svc.get_throttle_plan(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/campaigns/{campaign_id}/queue")
async def get_queue_preview(
    campaign_id: int,
    ctx: TenantContextDep,
    limit: int = Query(20, ge=1, le=200),
):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    return await svc.queue_preview(campaign_id, limit=limit)


@router.post("/campaigns/{campaign_id}/claim")
async def claim_outbound_batch(
    campaign_id: int,
    ctx: TenantContextDep,
    batch_size: int | None = Query(None, ge=1, le=50),
):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    return await svc.claim_outbound_batch(campaign_id, batch_size=batch_size)


@router.post("/campaigns/{campaign_id}/refresh-priorities")
async def refresh_priorities(
    campaign_id: int,
    ctx: TenantContextDep,
):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    return await svc.refresh_priorities(campaign_id, organization_id=ctx.organization_id)


@router.post("/retries")
async def schedule_retry(body: ScheduleRetryRequest, ctx: TenantContextDep):
    svc = get_voice_campaign_service()
    result = await svc.schedule_retry_for_run(body.queued_run_id, reason=body.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="Queued run not found")
    return result


@router.get("/campaigns/{campaign_id}/analytics", response_model=CampaignAnalyticsSchema)
async def campaign_analytics(campaign_id: int, ctx: TenantContextDep):
    await assert_campaign_belongs_to_tenant(ctx, campaign_id)
    svc = get_voice_campaign_service()
    data = await svc.get_analytics(campaign_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignAnalyticsSchema(**data)
