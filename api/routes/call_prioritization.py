"""API routes for predictive call prioritization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db.models import UserModel
from api.schemas.call_prioritization import (
    EnqueueCustomerRequest,
    PrioritizationScoreSchema,
    PrioritizeBatchRequest,
    QueueSnapshotSchema,
    RecordCallOutcomeRequest,
)
from api.services.auth.depends import get_user
from api.services.call_prioritization.service import get_call_prioritization_service
from api.services.tenant import get_tenant_context
from api.services.tenant.types import TenantContext

router = APIRouter(prefix="/call-prioritization", tags=["call-prioritization"])


async def get_organization_id(ctx: TenantContext = Depends(get_tenant_context)) -> int:
    return ctx.organization_id


@router.get("/status")
async def prioritization_status(_user=Depends(get_user)):
    svc = get_call_prioritization_service()
    return {"enabled": svc.enabled}


@router.get("/score/{customer_id}", response_model=PrioritizationScoreSchema)
async def score_customer(
    customer_id: int,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Call prioritization is disabled")
    result = await svc.score_customer(customer_id, organization_id=organization_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return PrioritizationScoreSchema(**result.to_dict())


@router.post("/prioritize", response_model=list[PrioritizationScoreSchema])
async def prioritize_batch(
    body: PrioritizeBatchRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Call prioritization is disabled")
    results = await svc.prioritize_batch(
        body.customer_ids,
        organization_id=organization_id,
    )
    return [PrioritizationScoreSchema(**r.to_dict()) for r in results]


@router.post("/enqueue")
async def enqueue_customer(
    body: EnqueueCustomerRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Call prioritization is disabled")
    result = await svc.enqueue_customer(
        body.customer_id,
        organization_id=organization_id,
        attempt_number=body.attempt_number,
        workflow_run_id=body.workflow_run_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


@router.post("/refresh")
async def refresh_queue(
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    return await svc.refresh_queue(organization_id)


@router.get("/queue", response_model=QueueSnapshotSchema)
async def queue_snapshot(
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    return QueueSnapshotSchema(**await svc.queue_snapshot(organization_id))


@router.post("/dequeue")
async def dequeue_next(
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    entry = await svc.dequeue_next(organization_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue is empty")
    return entry


@router.post("/process-retries")
async def process_retries(
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    return await svc.process_due_retries(organization_id)


@router.post("/outcome")
async def record_outcome(
    body: RecordCallOutcomeRequest,
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    return await svc.record_outcome(
        body.customer_id,
        organization_id=organization_id,
        outcome=body.outcome,
        phone_e164=body.phone_e164,
        attempt_number=body.attempt_number,
        workflow_run_id=body.workflow_run_id,
        duration_s=body.duration_s,
    )


@router.get("/retries")
async def list_retries(
    limit: int = Query(50, ge=1, le=200),
    organization_id: int = Depends(get_organization_id),
    _user=Depends(get_user),
):
    svc = get_call_prioritization_service()
    snapshot = await svc.queue_snapshot(organization_id)
    return snapshot["retries"][:limit]
