"""Omnichannel customer timeline APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import CUSTOMER_TIMELINE_ENABLED
from api.schemas.customer_timeline import (
    CustomerTimelineSchema,
    JourneyStateSchema,
    TimelineEntrySchema,
)
from api.services.auth.depends import get_user
from api.services.customer_timeline.correlation import normalize_phone
from api.services.customer_timeline.service import get_customer_timeline_service
from api.services.tenant import assert_customer_belongs_to_tenant
from api.services.tenant.route_helpers import TenantContextDep

router = APIRouter(prefix="/customer-timeline", tags=["customer-timeline"])


def _require_enabled() -> None:
    if not CUSTOMER_TIMELINE_ENABLED:
        raise HTTPException(status_code=503, detail="Customer timeline is disabled")


@router.get("/status")
async def timeline_status(_user=Depends(get_user)):
    svc = get_customer_timeline_service()
    return {"enabled": svc.enabled}


@router.get("/customers/{customer_id}", response_model=CustomerTimelineSchema)
async def get_customer_timeline(
    customer_id: int,
    ctx: TenantContextDep,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
):
    _require_enabled()
    await assert_customer_belongs_to_tenant(ctx, customer_id)
    svc = get_customer_timeline_service()
    timeline = await svc.get_by_customer_id(
        customer_id,
        organization_id=ctx.organization_id,
        days=days,
        limit=limit,
    )
    if timeline is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    data = timeline.to_dict()
    return CustomerTimelineSchema(
        **data,
        entries=[TimelineEntrySchema(**e) for e in data["entries"]],
    )


@router.get("/phone/{phone_e164:path}", response_model=CustomerTimelineSchema)
async def get_phone_timeline(
    phone_e164: str,
    ctx: TenantContextDep,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
):
    _require_enabled()
    svc = get_customer_timeline_service()
    phone = normalize_phone(phone_e164) or phone_e164
    timeline = await svc.get_by_phone(
        organization_id=ctx.organization_id,
        phone_e164=phone,
        days=days,
        limit=limit,
    )
    data = timeline.to_dict()
    return CustomerTimelineSchema(
        **data,
        entries=[TimelineEntrySchema(**e) for e in data["entries"]],
    )


@router.get("/journey-state", response_model=JourneyStateSchema)
async def get_journey_state(
    ctx: TenantContextDep,
    phone_e164: str | None = Query(None),
    customer_id: int | None = Query(None),
):
    _require_enabled()
    if not phone_e164 and not customer_id:
        raise HTTPException(
            status_code=400,
            detail="Provide phone_e164 or customer_id",
        )
    if customer_id:
        await assert_customer_belongs_to_tenant(ctx, customer_id)
    svc = get_customer_timeline_service()
    phone = normalize_phone(phone_e164) if phone_e164 else None
    result = await svc.get_journey_state(
        organization_id=ctx.organization_id,
        phone_e164=phone,
        customer_id=customer_id,
    )
    return JourneyStateSchema(**result)
