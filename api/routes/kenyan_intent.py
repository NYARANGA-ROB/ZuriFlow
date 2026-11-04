"""FastAPI routes for Kenyan realtime business intent detection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.kenyan_intent import (
    ClassifyRequest,
    ClassifyResponse,
    ClassificationResultSchema,
    InterruptRequest,
    RouteDecisionSchema,
    RouteRequest,
    SessionSnapshotSchema,
    StatusSchema,
)
from api.services.auth.depends import get_user
from api.services.kenyan_intent.service import get_realtime_intent_service
from api.services.kenyan_intent.types import TranscriptKind
from api.services.tenant import assert_session_belongs_to_tenant, register_session_organization
from api.services.tenant.route_helpers import TenantContextDep

router = APIRouter(prefix="/kenyan-intent", tags=["kenyan-intent"])


def _result_schema(result) -> ClassificationResultSchema:
    data = result.to_dict()
    return ClassificationResultSchema(**data)


def _route_schema(route) -> RouteDecisionSchema:
    data = route.to_dict()
    return RouteDecisionSchema(**data)


@router.get("/status", response_model=StatusSchema)
async def intent_status(_user=Depends(get_user)):
    svc = get_realtime_intent_service()
    cfg = svc._config  # noqa: SLF001
    return StatusSchema(
        enabled=svc.enabled,
        use_normalization=cfg.use_normalization,
        partial_confidence_threshold=cfg.partial_confidence_threshold,
        route_confidence_threshold=cfg.route_confidence_threshold,
    )


@router.post("/classify", response_model=ClassifyResponse)
async def classify_intent(body: ClassifyRequest, ctx: TenantContextDep):
    svc = get_realtime_intent_service()
    session_id = body.session_id or f"api-classify-{ctx.organization_id}"
    await register_session_organization(session_id, ctx.organization_id)
    kind = TranscriptKind.PARTIAL if body.is_partial else TranscriptKind.FINAL
    result, route = await svc.infer(session_id, body.text, kind=kind)
    return ClassifyResponse(
        result=_result_schema(result),
        route=_route_schema(route),
        enabled=svc.enabled,
    )


@router.post("/route", response_model=ClassifyResponse)
async def classify_and_route(body: RouteRequest, ctx: TenantContextDep):
    svc = get_realtime_intent_service()
    session_id = body.session_id or f"api-route-{ctx.organization_id}"
    await register_session_organization(session_id, ctx.organization_id)
    kind = TranscriptKind.PARTIAL if body.is_partial else TranscriptKind.FINAL
    result, route = await svc.infer(session_id, body.text, kind=kind)
    return ClassifyResponse(
        result=_result_schema(result),
        route=_route_schema(route),
        enabled=svc.enabled,
    )


@router.get("/session/{session_id}", response_model=SessionSnapshotSchema)
async def get_session(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_realtime_intent_service()
    snap = svc.get_session_snapshot(session_id)
    if not snap.get("exists"):
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionSnapshotSchema(
        session_id=snap["session_id"],
        current_intent=snap.get("current_intent", "unknown"),
        confidence=float(snap.get("confidence", 0.0)),
        slots=snap.get("slots", {}),
        history=snap.get("history", []),
        interrupted=bool(snap.get("interrupted", False)),
        language=snap.get("language", "mixed"),
        last_result=_result_schema(snap["last_result"]) if snap.get("last_result") else None,
        last_route=_route_schema(snap["last_route"]) if snap.get("last_route") else None,
    )


@router.post("/session/{session_id}/interrupt")
async def mark_interrupt(
    session_id: str,
    body: InterruptRequest,
    ctx: TenantContextDep,
):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_realtime_intent_service()
    state = svc.on_interrupt(session_id, partial_text=body.partial_text)
    return state.to_dict()


@router.post("/session/{session_id}/resume")
async def mark_resume(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_realtime_intent_service()
    state = svc.on_resume(session_id)
    return state.to_dict()


@router.delete("/session/{session_id}")
async def end_session(session_id: str, ctx: TenantContextDep):
    await assert_session_belongs_to_tenant(ctx, session_id)
    svc = get_realtime_intent_service()
    snap = svc.end_session(session_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return snap
