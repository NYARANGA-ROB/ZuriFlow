"""FastAPI routes for Kenyan debt collection AI workflow."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.debt_collection import (
    ComplianceAuditSchema,
    ComplianceCheckRequest,
    DebtCollectionResponse,
    NegotiateRequest,
    PaymentStatusRequest,
    SessionDetailSchema,
    StartDebtCollectionRequest,
    TranscriptRequest,
)
from api.services.auth.depends import get_user
from api.services.tenant import TenantContext, assert_same_tenant, get_tenant_context, scoped_organization_id
from api.services.debt_collection.compliance.service import get_compliance_guardrail_service
from api.services.debt_collection.compliance.types import SpeakerRole
from api.services.debt_collection.engine import get_debt_collection_engine
from api.services.debt_collection.types import DebtAccount

router = APIRouter(prefix="/debt-collection", tags=["debt-collection"])


def _require_session(session_id: str, ctx: TenantContext):
    engine = get_debt_collection_engine()
    session = engine.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    assert_same_tenant(ctx, session.organization_id)
    return engine, session


def _response(data: dict) -> DebtCollectionResponse:
    return DebtCollectionResponse(**data)


@router.get("/status")
async def debt_collection_status(_user=Depends(get_user)):
    engine = get_debt_collection_engine()
    compliance = get_compliance_guardrail_service()
    return {
        "enabled": engine.enabled,
        "template_id": engine.TEMPLATE_ID,
        "compliance": compliance.status(),
    }


@router.get("/compliance/status")
async def compliance_status(_user=Depends(get_user)):
    return get_compliance_guardrail_service().status()


@router.post("/compliance/check")
async def compliance_check(body: ComplianceCheckRequest, _user=Depends(get_user)):
    speaker = SpeakerRole(body.speaker) if body.speaker in ("agent", "customer") else SpeakerRole.AGENT
    return get_compliance_guardrail_service().check_text(body.text, speaker=speaker)


@router.get("/sessions/{session_id}/compliance/audit", response_model=ComplianceAuditSchema)
async def get_compliance_audit(
    session_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    engine, session = _require_session(session_id, ctx)
    svc = get_compliance_guardrail_service()
    entries = await svc.get_audit_log(session, session_id)
    return ComplianceAuditSchema(
        session_id=session_id,
        entries=entries,
        violation_count=int(session.variables.get("compliance_violation_count", 0)),
    )


@router.post("/sessions", response_model=DebtCollectionResponse)
async def start_debt_collection(
    body: StartDebtCollectionRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    engine = get_debt_collection_engine()
    if not engine.enabled:
        raise HTTPException(status_code=503, detail="Debt collection workflow is disabled")
    org_id = scoped_organization_id(ctx, body.organization_id)
    account = DebtAccount(**body.account.model_dump())
    data = await engine.start(
        organization_id=org_id,
        account=account,
        workflow_run_id=body.workflow_run_id,
        locale=body.locale,
        session_id=body.session_id,
    )
    return _response(data)


@router.get("/sessions/{session_id}", response_model=SessionDetailSchema)
async def get_debt_session(
    session_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    _, session = _require_session(session_id, ctx)
    return SessionDetailSchema(
        session_id=session.session_id,
        organization_id=session.organization_id,
        workflow_run_id=session.workflow_run_id,
        vertical_instance_id=session.vertical_instance_id,
        locale=session.locale,
        negotiation_outcome=session.outcome.value,
        escalation_risk=session.escalation_risk.value,
        negotiation_rounds=session.negotiation_rounds,
        refusal_count=session.refusal_count,
        interruption_count=session.interruption_count,
        commitments=[c.to_dict() for c in session.commitments],
        installment_plan=(
            session.installment_plan.to_dict() if session.installment_plan else None
        ),
        account=session.account.to_dict() if session.account else None,
    )


@router.post("/sessions/{session_id}/transcript", response_model=DebtCollectionResponse)
async def handle_transcript(
    session_id: str,
    body: TranscriptRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    engine, _ = _require_session(session_id, ctx)
    try:
        data = await engine.handle_transcript(
            session_id,
            body.text,
            is_final=body.is_final,
            interrupted=body.interrupted,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return _response(data)


@router.post("/sessions/{session_id}/negotiate", response_model=DebtCollectionResponse)
async def negotiate_payment(
    session_id: str,
    body: NegotiateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    engine, _ = _require_session(session_id, ctx)
    try:
        data = await engine.negotiate(
            session_id,
            customer_offer_amount=body.customer_offer_amount,
            accept=body.accept,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _response(data)


@router.post("/sessions/{session_id}/installment/approve", response_model=DebtCollectionResponse)
async def approve_installment_plan(
    session_id: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    engine, _ = _require_session(session_id, ctx)
    try:
        data = await engine.approve_installment_plan(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _response(data)


@router.post("/sessions/{session_id}/payment", response_model=DebtCollectionResponse)
async def record_payment_status(
    session_id: str,
    body: PaymentStatusRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    engine, _ = _require_session(session_id, ctx)
    try:
        data = await engine.record_payment(
            session_id,
            status=body.status,
            amount=body.amount,
            receipt=body.receipt,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return _response(data)
