"""APIs for voice cost optimization and analytics."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import VOICE_COST_OPTIMIZATION_ENABLED
from api.schemas.voice_cost_optimization import (
    CostAnalyticsSchema,
    ResolveTurnRequest,
    SessionCostSchema,
    VoiceCostStatusSchema,
)
from api.services.auth.depends import get_user
from api.services.tenant import assert_session_belongs_to_tenant, scoped_organization_id
from api.services.tenant.route_helpers import AnalyticsReadContext, TenantContextDep
from api.services.voice_cost_optimization.service import get_voice_cost_optimization_service

router = APIRouter(prefix="/voice-cost-optimization", tags=["voice-cost-optimization"])


def _require_enabled() -> None:
    if not VOICE_COST_OPTIMIZATION_ENABLED:
        raise HTTPException(
            status_code=503, detail="Voice cost optimization is disabled"
        )


@router.get("/status", response_model=VoiceCostStatusSchema)
async def cost_optimization_status(_user=Depends(get_user)):
    return VoiceCostStatusSchema(**get_voice_cost_optimization_service().status())


@router.post("/resolve")
async def resolve_turn(body: ResolveTurnRequest, ctx: TenantContextDep):
    _require_enabled()
    org_id = scoped_organization_id(
        ctx, body.organization_id if body.organization_id > 0 else None
    )
    svc = get_voice_cost_optimization_service()
    resolution = await svc.resolve_turn(
        body.text,
        organization_id=org_id,
        locale=body.locale,
        turn_count=body.turn_count,
        intent=body.intent,
        intent_confidence=body.intent_confidence,
    )
    return resolution.to_dict()


@router.get("/analytics", response_model=CostAnalyticsSchema)
async def cost_analytics(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    now = time.time()
    start = from_ts if from_ts is not None else now - days * 86400
    end = to_ts if to_ts is not None else now
    snapshot = await get_voice_cost_optimization_service().get_cost_analytics(
        org_id, from_ts=start, to_ts=end
    )
    return CostAnalyticsSchema(**snapshot.to_dict())


@router.get("/sessions/{session_id}/cost", response_model=SessionCostSchema)
async def session_cost(session_id: str, ctx: TenantContextDep):
    _require_enabled()
    await assert_session_belongs_to_tenant(ctx, session_id)
    data = await get_voice_cost_optimization_service().analytics().session_summary(
        session_id
    )
    return SessionCostSchema(**data)


@router.get("/cache/stats")
async def cache_stats(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    return await get_voice_cost_optimization_service().cache().stats(org_id)
