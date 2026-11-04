"""Operator dashboard APIs for human escalation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db.models import UserModel
from api.schemas.human_escalation import (
    ClaimEscalationRequest,
    HandoffPackageSchema,
    ManualEscalateRequest,
    OperatorClaimSchema,
    TransferHandoffRequest,
)
from api.services.auth.depends import get_user
from api.services.human_escalation.service import get_human_escalation_service
from api.services.tenant import assert_session_belongs_to_tenant, get_tenant_context
from api.services.tenant.route_helpers import TenantContextDep
from api.services.tenant.types import TenantContext

router = APIRouter(prefix="/human-escalation", tags=["human-escalation"])


async def get_organization_id(
    ctx: TenantContext = Depends(get_tenant_context),
) -> int:
    return ctx.organization_id


@router.get("/status")
async def escalation_status(_user=Depends(get_user)):
    svc = get_human_escalation_service()
    return {"enabled": svc.enabled}


@router.get("/dashboard")
async def operator_dashboard(
    organization_id: int = Depends(get_organization_id),
):
    svc = get_human_escalation_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Human escalation is disabled")
    return await svc.dashboard_summary(organization_id)


@router.get("/pending")
async def list_pending_escalations(
    organization_id: int = Depends(get_organization_id),
    limit: int = Query(50, ge=1, le=200),
):
    svc = get_human_escalation_service()
    summary = await svc.dashboard_summary(organization_id)
    return summary["pending"][:limit]


@router.get("/queues/{queue_name}")
async def list_escalation_queue(
    queue_name: str,
    organization_id: int = Depends(get_organization_id),
    limit: int = Query(20, ge=1, le=100),
):
    svc = get_human_escalation_service()
    return await svc.list_queue(organization_id, queue_name, limit=limit)


@router.post("/escalate")
async def manual_escalate(
    body: ManualEscalateRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_human_escalation_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Human escalation is disabled")
    return await svc.escalate_manual(
        session_id=body.session_id,
        organization_id=organization_id,
        reason=body.reason,
        intent=body.intent,
        language=body.language,
        workflow_run_id=body.workflow_run_id,
        phone_e164=body.phone_e164,
        call_sid=body.call_sid,
        customer_name=body.customer_name,
        queue_name=body.queue_name,
        priority=body.priority,
        risk_level=body.risk_level,
        operator_id=user.id,
    )


@router.post("/claim", response_model=OperatorClaimSchema | None)
async def claim_escalation(
    body: ClaimEscalationRequest,
    organization_id: int = Depends(get_organization_id),
    user: UserModel = Depends(get_user),
):
    svc = get_human_escalation_service()
    claim = await svc.claim_next(
        organization_id,
        body.queue_name,
        operator_id=user.id,
    )
    if claim is None:
        return None
    return OperatorClaimSchema(**claim.to_dict())


@router.get("/handoff/{session_id}", response_model=HandoffPackageSchema)
async def get_handoff_package(
    session_id: str,
    ctx: TenantContextDep,
):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_human_escalation_service()
    handoff = await svc.get_handoff(session_id)
    if handoff is None:
        raise HTTPException(status_code=404, detail="Handoff not found")
    return HandoffPackageSchema(**handoff)


@router.post("/handoff/{session_id}/transfer")
async def transfer_to_human(
    session_id: str,
    body: TransferHandoffRequest,
    ctx: TenantContextDep,
):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_human_escalation_service()
    return await svc.transfer_claimed(
        session_id,
        destination=body.destination,
        timeout_seconds=body.timeout_seconds,
    )


@router.post("/handoff/{session_id}/resolve")
async def resolve_escalation(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_human_escalation_service()
    ok = await svc.resolve(session_id)
    return {"resolved": ok, "session_id": session_id}
