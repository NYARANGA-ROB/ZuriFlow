"""FastAPI routes for durable workflow orchestration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.constants import DURABLE_EXECUTION_ENABLED
from api.schemas.durable_execution import (
    DurableExecutionStatusSchema,
    OrchestrationEventSchema,
    OrchestrationResultSchema,
    OrchestrationSummarySchema,
    SignalOrchestrationRequest,
    StartOrchestrationRequest,
)
from api.services.auth.depends import get_user
from api.services.durable_execution.definitions import get_definition_registry
from api.services.durable_execution.persistence import get_orchestration_persistence
from api.services.durable_execution.resumable_manager import get_resumable_workflow_manager
from api.services.durable_execution.runtime import get_durable_execution_runtime
from api.services.tenant.route_helpers import TenantContextDep

router = APIRouter(prefix="/durable-orchestrations", tags=["durable-orchestrations"])


@router.get("/status", response_model=DurableExecutionStatusSchema)
async def durable_execution_status(_user=Depends(get_user)):
    registry = get_definition_registry()
    return DurableExecutionStatusSchema(
        enabled=DURABLE_EXECUTION_ENABLED,
        definitions=registry.list_names(),
    )


@router.get("", response_model=list[OrchestrationSummarySchema])
async def list_orchestrations(
    ctx: TenantContextDep,
    status: str | None = Query(None),
    definition_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not DURABLE_EXECUTION_ENABLED:
        raise HTTPException(status_code=503, detail="Durable execution is disabled")
    persistence = get_orchestration_persistence()
    rows = await persistence.list_orchestrations(
        ctx.organization_id,
        status=status,
        definition_name=definition_name,
        limit=limit,
        offset=offset,
    )
    return [
        OrchestrationSummarySchema(
            id=row.id,
            organization_id=row.organization_id,
            definition_name=row.definition_name,
            orchestration_key=row.orchestration_key,
            status=row.status,
            current_step=row.current_step,
            workflow_run_id=row.workflow_run_id,
            error_message=row.error_message,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            completed_at=row.completed_at.isoformat() if row.completed_at else None,
        )
        for row in rows
    ]


@router.post("/start", response_model=OrchestrationResultSchema)
async def start_orchestration(body: StartOrchestrationRequest, ctx: TenantContextDep):
    if not DURABLE_EXECUTION_ENABLED:
        raise HTTPException(status_code=503, detail="Durable execution is disabled")
    runtime = get_durable_execution_runtime()
    try:
        result = await runtime.start(
            body.definition_name,
            ctx.organization_id,
            orchestration_key=body.orchestration_key,
            workflow_run_id=body.workflow_run_id,
            initial_state=body.initial_state,
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OrchestrationResultSchema(**result.to_dict())


@router.post("/{orchestration_id}/signal", response_model=OrchestrationResultSchema)
async def signal_orchestration(
    orchestration_id: int,
    body: SignalOrchestrationRequest,
    ctx: TenantContextDep,
):
    if not DURABLE_EXECUTION_ENABLED:
        raise HTTPException(status_code=503, detail="Durable execution is disabled")
    runtime = get_durable_execution_runtime()
    try:
        result = await runtime.signal(
            orchestration_id,
            body.signal_type,
            body.payload,
            organization_id=ctx.organization_id,
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OrchestrationResultSchema(**result.to_dict())


@router.get("/{orchestration_id}", response_model=OrchestrationResultSchema)
async def get_orchestration(orchestration_id: int, ctx: TenantContextDep):
    runtime = get_durable_execution_runtime()
    result = await runtime.get_status(
        orchestration_id,
        organization_id=ctx.organization_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    return OrchestrationResultSchema(**result.to_dict())


@router.get("/{orchestration_id}/events", response_model=list[OrchestrationEventSchema])
async def list_orchestration_events(
    orchestration_id: int,
    ctx: TenantContextDep,
    limit: int = 100,
):
    persistence = get_orchestration_persistence()
    row = await persistence.get_orchestration(
        orchestration_id,
        organization_id=ctx.organization_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Orchestration not found")
    events = await persistence.list_events(orchestration_id, limit=limit)
    return [
        OrchestrationEventSchema(
            id=e.id,
            event_type=e.event_type,
            payload=dict(e.payload or {}),
            created_at=e.created_at.isoformat() if e.created_at else None,
        )
        for e in events
    ]


@router.post("/{orchestration_id}/resume", response_model=OrchestrationResultSchema)
async def resume_orchestration(orchestration_id: int, ctx: TenantContextDep):
    if not DURABLE_EXECUTION_ENABLED:
        raise HTTPException(status_code=503, detail="Durable execution is disabled")
    manager = get_resumable_workflow_manager()
    outcome = await manager.resume(orchestration_id)
    if not outcome.get("resumed"):
        raise HTTPException(status_code=409, detail=outcome.get("reason", "not resumable"))
    return OrchestrationResultSchema(**outcome["result"])
