"""FastAPI routes for realtime conversation memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.schemas.realtime_memory import (
    MemoryEventRequest,
    RetrieveRequest,
    RetrievalResponse,
    SnapshotResponse,
)
from api.services.auth.depends import get_user
from api.services.realtime_conversation_memory.service import get_conversation_memory_service
from api.services.tenant import assert_session_belongs_to_tenant, register_session_organization
from api.services.tenant.route_helpers import TenantContextDep

router = APIRouter(prefix="/conversation-memory", tags=["conversation-memory"])


@router.get("/status")
async def memory_status(_user=Depends(get_user)):
    svc = get_conversation_memory_service()
    return {"enabled": svc.enabled}


@router.post("/event")
async def record_event(body: MemoryEventRequest, ctx: TenantContextDep):
    svc = get_conversation_memory_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="conversation memory disabled")
    await register_session_organization(body.session_id, ctx.organization_id)
    mgr = svc.session(body.session_id)
    if body.user_text:
        mgr.on_user_turn(body.user_text)
    if body.interrupted:
        mgr.on_interruption(body.partial_assistant)
    if body.assistant_text is not None:
        mgr.on_assistant_complete(body.assistant_text, interrupted=body.interrupted)
    return {"ok": True}


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_context(body: RetrieveRequest, ctx: TenantContextDep):
    svc = get_conversation_memory_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="conversation memory disabled")
    await assert_session_belongs_to_tenant(ctx, body.session_id)
    svc.session(body.session_id)
    messages, result = await svc.prepare_messages(body.session_id, [])
    return RetrievalResponse(result=result.to_dict())


@router.get("/snapshot/{session_id}", response_model=SnapshotResponse)
async def get_snapshot(session_id: str, ctx: TenantContextDep):
    svc = get_conversation_memory_service()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="conversation memory disabled")
    await assert_session_belongs_to_tenant(ctx, session_id)
    snap = svc.session(session_id).snapshot()
    return SnapshotResponse(snapshot=snap.to_dict())


@router.delete("/session/{session_id}")
async def end_session(session_id: str, ctx: TenantContextDep):
    svc = get_conversation_memory_service()
    await assert_session_belongs_to_tenant(ctx, session_id)
    snap = svc.end_session(session_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"snapshot": snap.to_dict()}
