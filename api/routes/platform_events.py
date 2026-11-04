"""APIs for the centralized platform event bus."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import PLATFORM_EVENTS_ENABLED
from api.schemas.platform_events import (
    ObservabilitySnapshotSchema,
    PlatformEventSchema,
    PlatformEventStatusSchema,
    PublishEventRequest,
    PublishEventResponse,
    ReplayResultSchema,
)
from api.services.auth.depends import get_user
from api.services.platform_events.bus import get_platform_event_bus
from api.services.platform_events.dlq import get_platform_event_dlq
from api.services.platform_events.observability import get_platform_event_observability
from api.services.platform_events.replay import PlatformEventReplay
from api.services.platform_events.router import get_platform_event_router
from api.services.platform_events.schema import PlatformEvent, PlatformEventSource, PlatformEventType
from api.services.tenant import scoped_organization_id
from api.services.tenant.route_helpers import AnalyticsReadContext, TenantContextDep
from api.tasks.function_names import FunctionNames

router = APIRouter(prefix="/platform-events", tags=["platform-events"])


def _require_enabled() -> None:
    if not PLATFORM_EVENTS_ENABLED:
        raise HTTPException(status_code=503, detail="Platform events are disabled")


@router.get("/status", response_model=PlatformEventStatusSchema)
async def platform_events_status(_user=Depends(get_user)):
    return PlatformEventStatusSchema(
        enabled=PLATFORM_EVENTS_ENABLED,
        registered_handlers=get_platform_event_router().registered_types(),
    )


@router.post("/publish", response_model=PublishEventResponse)
async def publish_event(body: PublishEventRequest, ctx: TenantContextDep):
    _require_enabled()
    try:
        event_type = PlatformEventType(body.event_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown event type: {body.event_type}") from exc

    event = PlatformEvent(
        event_type=event_type,
        organization_id=ctx.organization_id,
        source=PlatformEventSource.API,
        payload=body.payload,
        correlation_id=body.correlation_id,
        idempotency_key=body.idempotency_key,
    )
    result = await get_platform_event_bus().publish(
        event,
        route_async=body.route_async,
    )
    return PublishEventResponse(**result)


@router.get("/events", response_model=list[PlatformEventSchema])
async def list_events(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    event_type: str | None = Query(None),
    correlation_id: str | None = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    from api.db import db_client

    from_ts = datetime.now(UTC) - timedelta(days=days)
    rows = await db_client.list_platform_events(
        organization_id=org_id,
        event_type=event_type,
        correlation_id=correlation_id,
        from_ts=from_ts,
        limit=limit,
    )
    return [
        PlatformEventSchema(
            event_id=row.event_id,
            event_type=row.event_type,
            organization_id=row.organization_id,
            source=row.source,
            correlation_id=row.correlation_id,
            payload=dict(row.payload or {}),
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]


@router.get("/dead-letter")
async def list_dead_letter(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    return await get_platform_event_dlq().list_entries(org_id, limit=limit)


@router.get("/observability", response_model=ObservabilitySnapshotSchema)
async def event_observability(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    data = await get_platform_event_observability().snapshot(org_id)
    return ObservabilitySnapshotSchema(**data)


@router.post("/replay", response_model=ReplayResultSchema)
async def replay_events(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    event_type: str | None = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    replay = PlatformEventReplay()
    from_ts = datetime.now(UTC) - timedelta(days=days)
    result = await replay.replay_organization(
        org_id,
        event_type=event_type,
        from_ts=from_ts,
        limit=limit,
    )
    return ReplayResultSchema(**result)


@router.post("/replay/{event_id}", response_model=ReplayResultSchema)
async def replay_single_event(event_id: str, ctx: TenantContextDep):
    _require_enabled()
    replay = PlatformEventReplay()
    result = await replay.replay_event(event_id)
    return ReplayResultSchema(**result)


@router.post("/retries/process")
async def process_retries(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    from api.tasks.arq import enqueue_job

    job = await enqueue_job(
        FunctionNames.PROCESS_PLATFORM_EVENT_RETRIES,
        {"organization_id": org_id},
    )
    return {"queued": True, "job_id": job.job_id if job else None}
