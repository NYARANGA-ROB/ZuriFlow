"""APIs for production call reliability and recovery."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import CALL_RELIABILITY_ENABLED
from api.schemas.call_reliability import (
    FailureSummarySchema,
    RecordFailureRequest,
    ReliabilityStatusSchema,
    ReplayResultSchema,
)
from api.services.auth.depends import get_user
from api.services.call_reliability.service import get_call_reliability_service
from api.services.call_reliability.types import FailureSeverity
from api.services.tenant import (
    assert_session_belongs_to_tenant,
    assert_workflow_run_belongs_to_tenant,
    scoped_organization_id,
)
from api.services.tenant.route_helpers import AnalyticsReadContext, TenantContextDep
from api.tasks.arq import enqueue_job
from api.tasks.function_names import FunctionNames

router = APIRouter(prefix="/call-reliability", tags=["call-reliability"])


def _require_enabled() -> None:
    if not CALL_RELIABILITY_ENABLED:
        raise HTTPException(status_code=503, detail="Call reliability is disabled")


@router.get("/status", response_model=ReliabilityStatusSchema)
async def reliability_status(_user=Depends(get_user)):
    return ReliabilityStatusSchema(**get_call_reliability_service().status())


@router.post("/failures")
async def record_failure(
    body: RecordFailureRequest,
    ctx: TenantContextDep,
):
    _require_enabled()
    org_id = scoped_organization_id(
        ctx, body.organization_id if body.organization_id else None
    )
    result = await get_call_reliability_service().record_call_failure(
        organization_id=org_id,
        reason=body.reason,
        workflow_run_id=body.workflow_run_id,
        session_id=body.session_id,
        severity=FailureSeverity.MEDIUM,
        payload=body.payload,
        schedule_retry=body.schedule_retry,
    )
    return result


@router.get("/failures/summary", response_model=FailureSummarySchema)
async def failure_summary(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    days: int = Query(7, ge=1, le=30),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    data = await get_call_reliability_service().failure_summary(org_id, days=days)
    return FailureSummarySchema(**data)


@router.get("/retry-queue")
async def list_retry_queue(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    return await get_call_reliability_service().list_pending_retries(
        org_id, limit=limit
    )


@router.post("/retry-queue/process")
async def process_retry_queue(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    job = await enqueue_job(
        FunctionNames.PROCESS_CALL_RELIABILITY_RETRIES,
        {"organization_id": org_id},
    )
    return {"queued": True, "job_id": job.job_id if job else None}


@router.get("/dead-letter")
async def list_dead_letter(
    ctx: AnalyticsReadContext,
    organization_id: int = Query(..., gt=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_enabled()
    org_id = scoped_organization_id(ctx, organization_id)
    return await get_call_reliability_service().list_dlq(org_id, limit=limit)


@router.post("/replay/sessions/{session_id}", response_model=ReplayResultSchema)
async def replay_session_events(
    session_id: str,
    ctx: TenantContextDep,
):
    _require_enabled()
    await assert_session_belongs_to_tenant(ctx, session_id)
    result = await get_call_reliability_service().replay_session(session_id)
    return ReplayResultSchema(**result)


@router.post("/replay/workflows/{workflow_run_id}", response_model=ReplayResultSchema)
async def replay_workflow_events(
    workflow_run_id: int,
    ctx: TenantContextDep,
):
    _require_enabled()
    await assert_workflow_run_belongs_to_tenant(ctx, workflow_run_id)
    result = await get_call_reliability_service().replay_workflow(workflow_run_id)
    return ReplayResultSchema(**result)


@router.get("/events/sessions/{session_id}")
async def list_session_events(
    session_id: str,
    ctx: TenantContextDep,
    limit: int = Query(100, ge=1, le=500),
):
    _require_enabled()
    await assert_session_belongs_to_tenant(ctx, session_id)
    from api.services.call_reliability.event_store import get_durable_event_store

    events = await get_durable_event_store().list_session_events(
        session_id, limit=limit
    )
    return [e.to_dict() for e in events]


@router.get("/checkpoints/{session_id}")
async def get_ws_checkpoint(session_id: str, ctx: TenantContextDep):
    _require_enabled()
    await assert_session_belongs_to_tenant(ctx, session_id)
    state = await get_call_reliability_service().restore_ws_checkpoint(session_id)
    return {"session_id": session_id, "state": state}
