"""FastAPI routes for intelligent call routing."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.call_routing import (
    CallRoutingPlanSchema,
    CallRoutingResultSchema,
    DequeueRequest,
    EscalateRequest,
    QueueEntrySchema,
    RouteFromIntentRequest,
    RoutingStatusSchema,
)
from api.services.auth.depends import get_user
from api.services.tenant import (
    TenantContext,
    assert_session_belongs_to_tenant,
    get_tenant_context,
    register_session_organization,
    scoped_organization_id,
)
from api.services.tenant.route_helpers import TenantContextDep
from api.services.call_routing.escalation_manager import CallEscalationManager
from api.services.call_routing.integration import route_call_from_intent
from api.services.call_routing.orchestrator import get_call_routing_orchestrator
from api.services.call_routing.queue_service import CallRoutingQueueService
from api.services.call_routing.types import EscalationRequest
from api.services.kenyan_intent.service import get_realtime_intent_service
from api.services.kenyan_intent.types import TranscriptKind

router = APIRouter(prefix="/call-routing", tags=["call-routing"])


def _plan_schema(plan) -> CallRoutingPlanSchema:
    return CallRoutingPlanSchema(**plan.to_dict())


def _result_schema(result) -> CallRoutingResultSchema:
    data = result.to_dict()
    if data.get("plan"):
        data["plan"] = CallRoutingPlanSchema(**data["plan"])
    return CallRoutingResultSchema(**data)


@router.get("/status", response_model=RoutingStatusSchema)
async def routing_status(_user=Depends(get_user)):
    orch = get_call_routing_orchestrator()
    cfg = orch._config  # noqa: SLF001
    return RoutingStatusSchema(
        enabled=orch.enabled,
        queue_ttl_s=cfg.queue_ttl_s,
        route_confidence_threshold=cfg.route_confidence_threshold,
    )


@router.post("/route", response_model=CallRoutingResultSchema)
async def route_call(
    body: RouteFromIntentRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    org_id = scoped_organization_id(ctx, body.organization_id)
    await register_session_organization(body.session_id, org_id)
    intent_svc = get_realtime_intent_service()
    result, route = await intent_svc.infer(
        body.session_id,
        body.text,
        kind=TranscriptKind.FINAL,
    )
    if route is None:
        raise HTTPException(status_code=400, detail="Intent routing unavailable")

    routing = await route_call_from_intent(
        route,
        session_id=body.session_id,
        organization_id=org_id,
        workflow_run_id=body.workflow_run_id,
        phone_e164=body.phone_e164,
        customer_name=body.customer_name,
        call_sid=body.call_sid,
        language=body.language or result.language,
    )
    if routing is None:
        return CallRoutingResultSchema(status="pending")
    return _result_schema(routing)


@router.get("/session/{session_id}", response_model=CallRoutingResultSchema)
async def get_session_routing(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    orch = get_call_routing_orchestrator()
    result = orch.last_result(session_id)
    if result is None:
        position = await orch.queue_position(session_id)
        if position is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return CallRoutingResultSchema(status="queued", queue_position=position)
    return _result_schema(result)


@router.get("/queue/{organization_id}/{queue_name}")
async def list_queue(
    organization_id: int,
    queue_name: str,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    limit: int = 20,
):
    org_id = scoped_organization_id(ctx, organization_id)
    svc = CallRoutingQueueService()
    items = await svc.list_queue(org_id, queue_name, limit=limit)
    depth = await svc.depth(org_id, queue_name)
    return {"depth": depth, "items": items}


@router.post("/queue/dequeue", response_model=QueueEntrySchema | None)
async def dequeue_call(
    body: DequeueRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    org_id = scoped_organization_id(ctx, body.organization_id)
    orch = get_call_routing_orchestrator()
    entry = await orch.dequeue_for_agent(org_id, body.queue_name)
    if entry is None:
        return None
    return QueueEntrySchema(**entry.to_dict())


@router.post("/escalate")
async def escalate_call(
    body: EscalateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
):
    org_id = scoped_organization_id(ctx, body.organization_id)
    orch = get_call_routing_orchestrator()
    org_config = await orch.load_org_config(org_id)
    manager = CallEscalationManager()
    result = await manager.escalate(
        EscalationRequest(
            session_id=body.session_id,
            organization_id=org_id,
            reason=body.reason,
            intent=body.intent,
            language=body.language,
            workflow_run_id=body.workflow_run_id,
            phone_e164=body.phone_e164,
            call_sid=body.call_sid,
            context=body.context,
            queue_name=body.queue_name,
        ),
        org_config=org_config,
    )
    return result


@router.delete("/session/{session_id}")
async def end_routing_session(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    orch = get_call_routing_orchestrator()
    result = await orch.end_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.to_dict()
