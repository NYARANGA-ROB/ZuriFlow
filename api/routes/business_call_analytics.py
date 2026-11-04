"""Production-grade analytics APIs for AI business calls."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from api.constants import BUSINESS_CALL_ANALYTICS_ENABLED
from api.schemas.business_call_analytics import (
    AnalyticsSchemaResponse,
    BusinessAnalyticsStatusSchema,
    BusinessMetricsSchema,
    BusinessReportSchema,
    KpiValueSchema,
    TimeseriesPointSchema,
)
from api.services.auth.depends import get_user
from api.services.business_call_analytics.schema import BUSINESS_CALL_KPIS, TIMESERIES_KPIS
from api.services.business_call_analytics.service import get_business_call_analytics_service
from api.services.tenant import scoped_organization_id
from api.services.tenant.route_helpers import AnalyticsReadContext
from api.tasks.arq import enqueue_job
from api.tasks.function_names import FunctionNames

router = APIRouter(prefix="/business-call-analytics", tags=["business-call-analytics"])


def _require_enabled() -> None:
    if not BUSINESS_CALL_ANALYTICS_ENABLED:
        raise HTTPException(
            status_code=503, detail="Business call analytics is disabled"
        )


def _metrics_schema(snapshot) -> BusinessMetricsSchema:
    return BusinessMetricsSchema(
        organization_id=snapshot.organization_id,
        from_ts=snapshot.from_ts,
        to_ts=snapshot.to_ts,
        generated_at=snapshot.generated_at,
        total_calls=snapshot.total_calls,
        kpis={
            name: KpiValueSchema(**kpi.to_dict())
            for name, kpi in snapshot.kpis.items()
        },
        rates=dict(snapshot.rates),
    )


@router.get("/status", response_model=BusinessAnalyticsStatusSchema)
async def business_analytics_status(_user=Depends(get_user)):
    svc = get_business_call_analytics_service()
    data = svc.status()
    return BusinessAnalyticsStatusSchema(**data)


@router.get("/schema", response_model=AnalyticsSchemaResponse)
async def analytics_schema(_user=Depends(get_user)):
    _require_enabled()
    svc = get_business_call_analytics_service()
    return AnalyticsSchemaResponse(**svc.schema())


@router.get("/metrics", response_model=BusinessMetricsSchema)
async def get_metrics(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
    use_cache: bool = Query(True),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    now = time.time()
    start = from_ts if from_ts is not None else now - days * 86400
    end = to_ts if to_ts is not None else now
    svc = get_business_call_analytics_service()
    snapshot = await svc.get_metrics(
        org_id, from_ts=start, to_ts=end, use_cache=use_cache
    )
    return _metrics_schema(snapshot)


@router.get("/metrics/{kpi}", response_model=KpiValueSchema)
async def get_single_kpi(
    kpi: str,
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
):
    _require_enabled()
    if kpi not in BUSINESS_CALL_KPIS:
        raise HTTPException(status_code=404, detail=f"Unknown KPI: {kpi}")
    org_id = scoped_organization_id(ctx, organization_id)
    now = time.time()
    start = from_ts if from_ts is not None else now - days * 86400
    end = to_ts if to_ts is not None else now
    svc = get_business_call_analytics_service()
    try:
        value = await svc.get_kpi(org_id, kpi, from_ts=start, to_ts=end)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return KpiValueSchema(**value.to_dict())


@router.get("/timeseries", response_model=list[TimeseriesPointSchema])
async def get_timeseries(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    kpi: str = Query(...),
    granularity: str = Query("day", pattern="^(hour|day)$"),
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
):
    _require_enabled()
    if kpi not in TIMESERIES_KPIS:
        raise HTTPException(status_code=400, detail=f"Unsupported KPI: {kpi}")
    org_id = scoped_organization_id(ctx, organization_id)
    now = time.time()
    start = from_ts if from_ts is not None else now - days * 86400
    end = to_ts if to_ts is not None else now
    svc = get_business_call_analytics_service()
    points = await svc.get_timeseries(
        org_id,
        kpi,
        granularity=granularity,
        from_ts=start,
        to_ts=end,
    )
    return [TimeseriesPointSchema(**p.to_dict()) for p in points]


@router.get("/report", response_model=BusinessReportSchema)
async def get_report(
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
    svc = get_business_call_analytics_service()
    report = await svc.get_report(org_id, from_ts=start, to_ts=end)
    return BusinessReportSchema(
        organization_id=report.organization_id,
        from_ts=report.from_ts,
        to_ts=report.to_ts,
        generated_at=report.generated_at,
        summary=_metrics_schema(report.summary),
        by_language=report.by_language,
        by_day=report.by_day,
        top_events=report.top_events,
    )


@router.post("/aggregate")
async def trigger_aggregate(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    from_ts: float | None = None,
    to_ts: float | None = None,
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    job = await enqueue_job(
        FunctionNames.AGGREGATE_BUSINESS_CALL_ANALYTICS,
        {
            "organization_id": org_id,
            "from_ts": from_ts,
            "to_ts": to_ts,
        },
    )
    return {"queued": True, "job_id": job.job_id if job else None}


@router.get("/export/metrics.csv")
async def export_metrics_csv(
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
    svc = get_business_call_analytics_service()
    snapshot = await svc.get_metrics(org_id, from_ts=start, to_ts=end)
    output, filename = svc.export_metrics_csv(snapshot)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/report.csv")
async def export_report_csv(
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
    svc = get_business_call_analytics_service()
    report = await svc.get_report(org_id, from_ts=start, to_ts=end)
    output, filename = svc.export_report_csv(report)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/metrics.json")
async def export_metrics_json(
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
    svc = get_business_call_analytics_service()
    snapshot = await svc.get_metrics(org_id, from_ts=start, to_ts=end)
    return JSONResponse(svc.export_metrics_json(snapshot))


@router.get("/export/report.json")
async def export_report_json(
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
    svc = get_business_call_analytics_service()
    report = await svc.get_report(org_id, from_ts=start, to_ts=end)
    return JSONResponse(svc.export_report_json(report))
