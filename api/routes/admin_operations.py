"""Admin dashboard APIs for AI call operations."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketState

from api.constants import ADMIN_OPERATIONS_ENABLED
from api.db.models import UserModel
from api.schemas.admin_operations import (
    AdminCapabilitiesSchema,
    AdminHealthSchema,
    CampaignSearchRequest,
    PaymentSearchRequest,
    WorkflowRunSearchRequest,
)
from api.services.admin_operations.service import get_admin_operations_service
from api.services.auth.depends import get_user_ws
from api.services.tenant.access_control import (
    require_permission,
    resolve_tenant_context,
)
from api.services.tenant.types import Permission, TenantContext

router = APIRouter(prefix="/admin-operations", tags=["admin-operations"])


def _require_enabled() -> None:
    if not ADMIN_OPERATIONS_ENABLED:
        raise HTTPException(
            status_code=503, detail="Admin operations dashboard is disabled"
        )


def _analytics_ctx(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
) -> TenantContext:
    _require_enabled()
    return ctx


def _billing_ctx(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.BILLING_READ))],
) -> TenantContext:
    _require_enabled()
    return ctx


@router.get("/capabilities", response_model=AdminCapabilitiesSchema)
async def get_capabilities(
    _ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
):
    return AdminCapabilitiesSchema(**get_admin_operations_service().capabilities())


@router.get("/health", response_model=AdminHealthSchema)
async def admin_health(
    _ctx: Annotated[TenantContext, Depends(require_permission(Permission.ANALYTICS_READ))],
):
    data = await get_admin_operations_service().health()
    return AdminHealthSchema(**data)


@router.get("/summary")
async def dashboard_summary(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    return await get_admin_operations_service().get_summary(
        ctx, from_ts=from_ts, to_ts=to_ts, days=days
    )


@router.get("/calls/live")
async def live_calls(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
) -> dict[str, Any]:
    return await get_admin_operations_service().live_calls(ctx.organization_id)


@router.get("/calls/recent")
async def recent_calls(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    return await get_admin_operations_service().recent_runs(
        ctx.organization_id, limit=limit, offset=offset
    )


@router.get("/payments/summary")
async def payments_summary(
    ctx: Annotated[TenantContext, Depends(_billing_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    return await get_admin_operations_service().payments_summary(
        ctx.organization_id, from_ts=from_ts, to_ts=to_ts, days=days
    )


@router.get("/campaigns")
async def list_campaigns(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    return await get_admin_operations_service().campaigns(
        ctx.organization_id, limit=limit, offset=offset
    )


@router.get("/campaigns/{campaign_id}")
async def campaign_detail(
    campaign_id: int,
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
) -> dict[str, Any]:
    detail = await get_admin_operations_service().campaign_detail(
        ctx.organization_id, campaign_id
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return detail


@router.get("/escalations/summary")
async def escalations_summary(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    days: int = Query(7, ge=1, le=30),
) -> dict[str, Any]:
    return await get_admin_operations_service().escalations_summary(
        ctx.organization_id, days=days
    )


@router.get("/workflows/performance")
async def workflow_performance(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    return await get_admin_operations_service().workflow_performance(
        ctx.organization_id,
        from_ts=from_ts,
        to_ts=to_ts,
        days=days,
        limit=limit,
    )


@router.get("/tenant/analytics")
async def tenant_analytics(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
) -> dict[str, Any]:
    return await get_admin_operations_service().tenant_analytics(
        ctx, from_ts=from_ts, to_ts=to_ts
    )


@router.post("/search/runs")
async def search_runs(
    body: WorkflowRunSearchRequest,
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
) -> dict[str, Any]:
    return await get_admin_operations_service().search.search_runs(
        ctx.organization_id,
        q=body.q,
        filters=body.filters,
        from_ts=body.from_ts,
        to_ts=body.to_ts,
        sort_by=body.sort_by,
        sort_order=body.sort_order,
        limit=body.limit,
        offset=body.offset,
    )


@router.post("/search/campaigns")
async def search_campaigns(
    body: CampaignSearchRequest,
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
) -> dict[str, Any]:
    return await get_admin_operations_service().search.search_campaigns(
        ctx.organization_id,
        q=body.q,
        state=body.state,
        limit=body.limit,
        offset=body.offset,
    )


@router.post("/search/payments")
async def search_payments(
    body: PaymentSearchRequest,
    ctx: Annotated[TenantContext, Depends(_billing_ctx)],
) -> dict[str, Any]:
    return await get_admin_operations_service().search.search_payments(
        ctx.organization_id,
        q=body.q,
        status=body.status,
        from_ts=body.from_ts,
        to_ts=body.to_ts,
        limit=body.limit,
        offset=body.offset,
    )


@router.get("/reports/summary")
async def report_summary_json(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    return await get_admin_operations_service().get_summary(
        ctx, from_ts=from_ts, to_ts=to_ts, days=days
    )


@router.get("/reports/summary.csv")
async def report_summary_csv(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
):
    summary = await get_admin_operations_service().get_summary(
        ctx, from_ts=from_ts, to_ts=to_ts, days=days
    )
    buf, filename = get_admin_operations_service().export_report_csv(summary)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/summary.json")
async def report_summary_download(
    ctx: Annotated[TenantContext, Depends(_analytics_ctx)],
    from_ts: float | None = None,
    to_ts: float | None = None,
    days: int = Query(7, ge=1, le=90),
):
    summary = await get_admin_operations_service().get_summary(
        ctx, from_ts=from_ts, to_ts=to_ts, days=days
    )
    buf, filename = get_admin_operations_service().export_report_json(summary)
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.websocket("/ws/live")
async def admin_live_websocket(
    websocket: WebSocket,
    days: int = Query(1, ge=1, le=7),
):
    """Realtime admin dashboard updates (snapshot polling + Redis pub/sub)."""
    if not ADMIN_OPERATIONS_ENABLED:
        await websocket.close(code=1013, reason="Admin operations disabled")
        return

    user: UserModel = await get_user_ws(websocket)
    await websocket.accept()

    try:
        ctx = await resolve_tenant_context(user)
        if not ctx.has_permission(Permission.ANALYTICS_READ):
            await websocket.close(code=1008, reason="Missing analytics:read permission")
            return

        hub = get_admin_operations_service().realtime
        stop = asyncio.Event()

        async def _reader() -> None:
            try:
                while websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                stop.set()

        reader = asyncio.create_task(_reader())
        try:
            async for payload in hub.stream_updates(ctx, days=days, stop_event=stop):
                if websocket.application_state != WebSocketState.CONNECTED:
                    break
                await websocket.send_json(payload)
        finally:
            stop.set()
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
    except WebSocketDisconnect:
        pass
    except HTTPException as e:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close(code=1008, reason=str(e.detail))
