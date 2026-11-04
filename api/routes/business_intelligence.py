"""Business intelligence HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.constants import BUSINESS_INTELLIGENCE_ENABLED
from api.services.business_intelligence.dashboards import DASHBOARDS
from api.services.business_intelligence.service import get_business_intelligence_service
from api.services.tenant.access_control import get_tenant_context, scoped_organization_id
from api.services.tenant.route_helpers import AnalyticsReadContext
from api.services.tenant.types import TenantContext

router = APIRouter(prefix="/business-intelligence", tags=["business-intelligence"])


class ClassifyConversationRequest(BaseModel):
    text: str = Field(min_length=1)
    workflow_run_id: int | None = None
    transferred: bool = False
    completed: bool = False
    county: str | None = None
    context: dict = Field(default_factory=dict)


def _require_enabled() -> None:
    if not BUSINESS_INTELLIGENCE_ENABLED:
        raise HTTPException(status_code=503, detail="Business intelligence is disabled")


@router.get("/status")
async def bi_status(
    ctx: TenantContext = Depends(get_tenant_context),
):
    svc = get_business_intelligence_service()
    return svc.capabilities(ctx)


@router.get("/snapshot")
async def bi_snapshot(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    days: int = Query(7, ge=1, le=90),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    svc = get_business_intelligence_service()
    snap = await svc.snapshot(org_id, days=days)
    from api.services.business_intelligence.insights import build_insights
    from api.services.business_intelligence.privacy import strip_sensitive_metrics
    from api.services.tenant.types import Permission

    include_payments = ctx.has_permission(Permission.PAYMENT_ANALYTICS_READ)
    include_excerpts = ctx.has_permission(Permission.CONVERSATION_PII_READ)
    payload = strip_sensitive_metrics(snap, include_payments=include_payments)
    if not include_excerpts:
        payload.pop("redacted_excerpt", None)
    return {
        **payload,
        "insights": build_insights(snap),
        "payments_visible": include_payments,
        "conversation_excerpts": include_excerpts,
    }


@router.get("/dashboards/{name}")
async def bi_dashboard(
    name: str,
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    days: int = Query(7, ge=1, le=90),
):
    _require_enabled()
    if name not in DASHBOARDS:
        raise HTTPException(status_code=404, detail="Unknown dashboard")
    org_id = scoped_organization_id(ctx, organization_id)
    svc = get_business_intelligence_service()
    return await svc.dashboard(org_id, name, days=days, ctx=ctx)


@router.post("/classify")
async def bi_classify(
    body: ClassifyConversationRequest,
    ctx: AnalyticsReadContext,
):
    _require_enabled()
    svc = get_business_intelligence_service()
    return await svc.classify_and_store(
        ctx.organization_id,
        text=body.text,
        workflow_run_id=body.workflow_run_id,
        context=body.context,
        transferred=body.transferred,
        completed=body.completed,
        county=body.county,
    )
