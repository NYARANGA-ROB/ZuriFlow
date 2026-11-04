"""Dashboard-ready APIs for voice workflow analytics."""

from __future__ import annotations

import time

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import (
    VOICE_ANALYTICS_ENABLED,
    VOICE_ANALYTICS_EVENT_TTL_S,
    VOICE_ANALYTICS_MAX_EVENTS_PER_ORG,
)
from api.schemas.voice_analytics import (
    AnalyticsStatusSchema,
    DashboardSummarySchema,
    EventSchema,
    TimeseriesPointSchema,
    TrackEventRequest,
)
from api.services.auth.depends import get_user
from api.services.tenant import scoped_organization_id
from api.services.tenant.route_helpers import AnalyticsReadContext
from api.services.voice_analytics.aggregator import VoiceAnalyticsAggregator
from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.schema import normalize_event
from api.services.voice_analytics.store import VoiceAnalyticsStore
from api.tasks.arq import enqueue_job
from api.tasks.function_names import FunctionNames

router = APIRouter(prefix="/voice-analytics", tags=["voice-analytics"])


@router.get("/status", response_model=AnalyticsStatusSchema)
async def analytics_status(_user=Depends(get_user)):
    return AnalyticsStatusSchema(
        enabled=VOICE_ANALYTICS_ENABLED,
        event_ttl_s=VOICE_ANALYTICS_EVENT_TTL_S,
        max_events_per_org=VOICE_ANALYTICS_MAX_EVENTS_PER_ORG,
    )


@router.post("/events")
async def track_event(
    body: TrackEventRequest,
    ctx: AnalyticsReadContext,
):
    if not VOICE_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Voice analytics disabled")
    try:
        payload = body.model_dump()
        if payload.get("organization_id") is not None:
            payload["organization_id"] = scoped_organization_id(
                ctx, int(payload["organization_id"])
            )
        else:
            payload["organization_id"] = ctx.organization_id
        event = normalize_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emitter = get_voice_analytics_emitter()
    await emitter.track_async(event)
    return {"event_id": event.event_id, "accepted": True}


@router.get("/events", response_model=list[EventSchema])
async def list_events(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    event_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    since_hours: int = Query(24, ge=1, le=168),
):
    org_id = scoped_organization_id(ctx, organization_id)
    store = VoiceAnalyticsStore()
    since_ts = time.time() - since_hours * 3600
    items = await store.list_events(
        org_id,
        event_type=event_type,
        limit=limit,
        since_ts=since_ts,
    )
    return [EventSchema(**item) for item in items]


@router.get("/dashboard", response_model=DashboardSummarySchema)
async def dashboard_summary(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
):
    org_id = scoped_organization_id(ctx, organization_id)
    now = time.time()
    start = from_ts if from_ts is not None else now - days * 86400
    end = to_ts if to_ts is not None else now
    aggregator = VoiceAnalyticsAggregator()
    summary = await aggregator.aggregate_organization(
        org_id,
        from_ts=start,
        to_ts=end,
    )
    rates = summary.get("metrics", {}).pop("rates", {})
    return DashboardSummarySchema(
        organization_id=org_id,
        from_ts=start,
        to_ts=end,
        generated_at=summary["generated_at"],
        metrics=summary["metrics"],
        rates=rates,
    )


@router.get("/timeseries", response_model=list[TimeseriesPointSchema])
async def metric_timeseries(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    metric: str = Query(
        ...,
        pattern="^(payment_success|whatsapp_delivery|escalation|interruption|response_latency|customer_sentiment)$",
    ),
    granularity: str = Query("hour", pattern="^(hour|day)$"),
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(1, ge=1, le=30),
):
    org_id = scoped_organization_id(ctx, organization_id)
    now = time.time()
    start = from_ts if from_ts is not None else now - days * 86400
    end = to_ts if to_ts is not None else now
    aggregator = VoiceAnalyticsAggregator()
    rows = await aggregator.timeseries(
        org_id,
        metric,
        granularity=granularity,
        from_ts=start,
        to_ts=end,
    )
    return [
        TimeseriesPointSchema(metric=metric, **row)
        for row in rows
    ]


@router.post("/aggregate")
async def trigger_aggregate(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
):
    org_id = scoped_organization_id(ctx, organization_id)
    job = await enqueue_job(
        FunctionNames.AGGREGATE_VOICE_ANALYTICS,
        {"organization_id": org_id},
    )
    return {"queued": True, "job_id": job.job_id if job else None}
