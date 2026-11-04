"""Business Digital Twin and live operations APIs."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from api.constants import BUSINESS_TWIN_ENABLED
from api.db import db_client
from api.services.business_twin import service
from api.services.business_twin.authority import rank_sources
from api.services.business_twin.interview import next_question
from api.services.business_twin.kenya import counties
from api.services.tenant.access_control import require_permission
from api.services.tenant.types import Permission, TenantContext
from api.tasks.arq import enqueue_job
from api.tasks.function_names import FunctionNames

router = APIRouter(prefix="/business", tags=["business-twin"])


def _enabled() -> None:
    if not BUSINESS_TWIN_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


class ProfileUpdate(BaseModel):
    legal_name: str | None = None
    trading_name: str | None = None
    description: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    website: str | None = None
    email: str | None = None
    phones: list[str] | None = None
    counties: list[str] | None = None
    service_areas: list[str] | None = None
    languages: list[str] | None = None
    hours: dict[str, Any] | None = None
    payment: dict[str, Any] | None = None


class WebsiteIngestRequest(BaseModel):
    url: str


class DocumentExtractRequest(BaseModel):
    filename: str
    mime_type: str | None = None
    text: str = ""
    size_bytes: int | None = None


class InterviewRequest(BaseModel):
    transcript: str
    turn_index: int = 0


class ConnectSourceRequest(BaseModel):
    provider_kind: str
    adapter_key: str = "generic"
    display_name: str
    schedule: str = "daily"
    webhook_secret: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    allowlisted_hosts: list[str] | None = None


class ApprovalRequest(BaseModel):
    decision: str
    reason: str | None = None


class ConflictResolveRequest(BaseModel):
    resolved_source: str


class AuthorityRequest(BaseModel):
    data_type: str
    ranked_sources: list[str]


class LocationRequest(BaseModel):
    name: str
    county: str | None = None
    address: str | None = None
    phone: str | None = None


class OfferingRequest(BaseModel):
    kind: str = "service"
    name: str
    description: str | None = None
    price_amount: float | None = None
    sku: str | None = None


@router.get("/health")
async def business_health(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    return await service.health_dashboard(ctx.organization_id)


@router.get("/profile")
async def get_profile(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    return await service.get_or_create_profile(ctx.organization_id)


@router.put("/profile")
async def put_profile(
    body: ProfileUpdate,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    return await service.save_profile(
        ctx.organization_id, body.model_dump(exclude_none=True), actor_user_id=ctx.user_id
    )


@router.get("/changes")
async def get_changes(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    return await service.inbox(ctx.organization_id)


@router.post("/changes/{change_id}/decision")
async def decide_change(
    change_id: int,
    body: ApprovalRequest,
    request: Request,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    ip = request.client.host if request.client else None
    try:
        return await service.approve_change(
            ctx.organization_id,
            change_id,
            decision=body.decision,
            reason=body.reason,
            actor_user_id=ctx.user_id,
            ip_address=ip,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int,
    body: ConflictResolveRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    row = await db_client.resolve_conflict(
        ctx.organization_id,
        conflict_id,
        resolved_source=body.resolved_source,
        user_id=ctx.user_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return {"id": row.id, "resolved_source": row.resolved_source}


@router.post("/website/import")
async def import_website(
    body: WebsiteIngestRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    try:
        return await service.ingest_website_for_org(
            ctx.organization_id, body.url, actor_user_id=ctx.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/extract")
async def extract_document(
    body: DocumentExtractRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    try:
        return await service.ingest_document_text(
            ctx.organization_id,
            filename=body.filename,
            mime_type=body.mime_type,
            text=body.text,
            size_bytes=body.size_bytes,
            actor_user_id=ctx.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/interview")
async def interview(
    body: InterviewRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    result = await service.apply_interview(
        ctx.organization_id, body.transcript, actor_user_id=ctx.user_id
    )
    result["next_question"] = next_question(body.turn_index)
    return result


@router.post("/locations")
async def add_location(
    body: LocationRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    row = await db_client.add_location(
        ctx.organization_id,
        name=body.name,
        county=body.county,
        address=body.address,
        phone=body.phone,
        source="business_admin",
        source_type="business_admin",
        status="verified",
        last_verified_at=datetime.now(UTC),
    )
    return {"id": row.id, "name": row.name}


@router.get("/locations")
async def list_locations(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    rows = await db_client.list_locations(ctx.organization_id)
    return {"items": [{"id": r.id, "name": r.name, "county": r.county, "address": r.address} for r in rows]}


@router.post("/offerings")
async def add_offering(
    body: OfferingRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    row = await db_client.add_offering(
        ctx.organization_id,
        kind=body.kind,
        name=body.name,
        description=body.description,
        price_amount=body.price_amount,
        sku=body.sku,
        source="business_admin",
        source_type="business_admin",
        status="verified",
        price_currency="KES",
    )
    return {"id": row.id, "name": row.name}


@router.get("/offerings")
async def list_offerings(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    rows = await db_client.list_offerings(ctx.organization_id)
    return {
        "items": [
            {"id": r.id, "kind": r.kind, "name": r.name, "price_amount": r.price_amount, "status": r.status}
            for r in rows
        ]
    }


@router.post("/sources")
async def connect_source(
    body: ConnectSourceRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    return await service.connect_source(
        ctx.organization_id,
        provider_kind=body.provider_kind,
        adapter_key=body.adapter_key,
        display_name=body.display_name,
        schedule=body.schedule,
        webhook_secret=body.webhook_secret,
        config=body.config,
        actor_user_id=ctx.user_id,
    )


@router.get("/sources")
async def list_sources(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    rows = await db_client.list_sources(ctx.organization_id)
    return {
        "items": [
            {
                "id": r.id,
                "provider_kind": r.provider_kind,
                "display_name": r.display_name,
                "schedule": r.schedule,
                "status": r.status,
                "is_live": r.is_live,
            }
            for r in rows
        ]
    }


@router.post("/sources/{source_id}/sync")
async def trigger_sync(
    source_id: int,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    await enqueue_job(FunctionNames.SYNC_BUSINESS_SOURCE, ctx.organization_id, source_id)
    return {"queued": True}


@router.put("/authority")
async def put_authority(
    body: AuthorityRequest,
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_WRITE))],
):
    _enabled()
    ranked = rank_sources(body.data_type, body.ranked_sources)
    row = await db_client.upsert_authority(ctx.organization_id, body.data_type, ranked)
    return {"data_type": row.data_type, "ranked_sources": row.ranked_sources_json}


@router.get("/counties")
async def list_counties(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    return {"items": counties()}


@router.get("/alerts")
async def list_alerts(
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.CONFIG_READ))],
):
    _enabled()
    rows = await db_client.list_alerts(ctx.organization_id)
    return {"items": [{"id": r.id, "title": r.title, "body": r.body, "severity": r.severity} for r in rows]}


@router.post("/tools/{tool_name}")
async def invoke_tool(
    tool_name: str,
    body: dict[str, Any],
    ctx: Annotated[TenantContext, Depends(require_permission(Permission.TOOL_INVOKE))],
):
    _enabled()
    return await service.execute_tool(ctx.organization_id, tool_name, body, actor="api")


@router.post("/webhooks/{organization_id}/{source_id}")
async def inbound_webhook(
    organization_id: int,
    source_id: int,
    request: Request,
    x_zuriflow_signature: Annotated[str | None, Header()] = None,
    x_zuriflow_timestamp: Annotated[str | None, Header()] = None,
    x_zuriflow_nonce: Annotated[str | None, Header()] = None,
):
    _enabled()
    source = await db_client.get_source(organization_id, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Unknown connected system")
    body = await request.body()
    from api.services.business_twin.cache import claim_nonce
    from api.services.business_twin.webhook_security import verify_signed_webhook

    secret = service.source_webhook_secret(source)
    error = verify_signed_webhook(
        secret,
        body,
        x_zuriflow_signature,
        timestamp=x_zuriflow_timestamp,
        nonce=x_zuriflow_nonce,
    )
    if error:
        raise HTTPException(status_code=401, detail=error)
    if x_zuriflow_nonce and not await claim_nonce(organization_id, x_zuriflow_nonce):
        raise HTTPException(status_code=401, detail="replay")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="malformed")
    event_type = str(payload.get("event_type") or payload.get("type") or "BUSINESS_UPDATED")
    await enqueue_job(
        FunctionNames.PROCESS_BUSINESS_EVENT,
        organization_id,
        source_id,
        event_type,
        payload.get("data") or payload,
    )
    return {"accepted": True}
