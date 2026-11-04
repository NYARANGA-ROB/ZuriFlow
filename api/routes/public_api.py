"""Public API platform REST endpoints."""

from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, Request

from api.constants import PUBLIC_API_ENABLED
from api.routes.public_agent import (
    TriggerCallRequest,
    TriggerCallResponse,
    _initiate_call,
    _resolve_trigger_target,
    _resolve_workflow_uuid_target,
)
from api.sdk_expose import sdk_expose
from api.schemas.public_api import (
    ApiUsageResponse,
    CreateWebhookRequest,
    GatewayInfoResponse,
    GatewayRouteResponse,
    PlatformTriggerCallRequest,
    UpdateWebhookRequest,
    WebhookDeliveryResponse,
    WebhookSubscriptionResponse,
)
from api.services.public_api.auth import get_public_api_context
from api.services.public_api.gateway import get_api_gateway
from api.services.public_api.types import PublicApiContext
from api.services.public_api.usage import get_public_api_usage_tracker
from api.services.public_api.webhook_manager import get_webhook_manager

router = APIRouter(prefix="/platform", tags=["platform"])


def _require_platform_enabled() -> None:
    if not PUBLIC_API_ENABLED:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Public API platform is disabled")


def _to_webhook_response(row, *, secret: str | None = None) -> WebhookSubscriptionResponse:
    return WebhookSubscriptionResponse(
        subscription_uuid=row.subscription_uuid,
        name=row.name,
        url=row.url,
        events=list(row.events or []),
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat() if row.created_at else None,
        secret=secret,
    )


@router.get("", response_model=GatewayInfoResponse, **sdk_expose(
    method="get_platform_info",
    description="Return public API gateway metadata and SDK pointers.",
))
async def gateway_info(
    _: Annotated[None, Depends(_require_platform_enabled)],
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> GatewayInfoResponse:
    del ctx
    return GatewayInfoResponse(**get_api_gateway().info())


@router.get("/docs")
async def platform_docs(
    _: Annotated[None, Depends(_require_platform_enabled)],
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> dict:
    """SDK-ready OpenAPI-style catalog for the public platform."""
    del ctx
    gw = get_api_gateway()
    return {
        "openapi": "3.0.3",
        "info": gw.info(),
        "paths": {
            route["path"]: {
                route["method"].lower(): {
                    "summary": route["description"],
                    "security": [{"ApiKeyAuth": []}],
                }
            }
            for route in gw.routes()
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
            }
        },
        "usage_dashboard": "/api/v1/tenant-billing/usage/summary",
        "webhooks": gw.info().get("webhooks"),
        "sdk": gw.info().get("sdk"),
    }


@router.get("/routes", response_model=List[GatewayRouteResponse])
async def gateway_routes(
    _: Annotated[None, Depends(_require_platform_enabled)],
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> List[GatewayRouteResponse]:
    del ctx
    return [GatewayRouteResponse(**route) for route in get_api_gateway().routes()]


@router.get("/usage", response_model=ApiUsageResponse, **sdk_expose(
    method="get_platform_usage",
    description="Return API usage analytics for the authenticated organization.",
))
async def platform_usage(
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
    scope: str = Query(default="organization", pattern="^(organization|api_key)$"),
) -> ApiUsageResponse:
    tracker = get_public_api_usage_tracker()
    api_key_id = ctx.api_key_id if scope == "api_key" else None
    bucket = await tracker.get_summary(ctx.organization_id, api_key_id=api_key_id)
    avg_latency = None
    if bucket.total_requests > 0:
        avg_latency = round(bucket.total_latency_ms / bucket.total_requests, 2)
    top_paths = dict(sorted((bucket.by_path or {}).items(), key=lambda x: -x[1])[:10])
    return ApiUsageResponse(
        organization_id=ctx.organization_id,
        api_key_id=api_key_id,
        total_requests=bucket.total_requests,
        error_requests=bucket.error_requests,
        avg_latency_ms=avg_latency,
        top_paths=top_paths,
    )


@router.get("/webhooks", response_model=List[WebhookSubscriptionResponse])
async def list_webhooks(
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> List[WebhookSubscriptionResponse]:
    rows = await get_webhook_manager().list_subscriptions(ctx.organization_id)
    return [_to_webhook_response(row) for row in rows]


@router.post("/webhooks", response_model=WebhookSubscriptionResponse, **sdk_expose(
    method="create_webhook_subscription",
    description="Register a webhook endpoint for platform events.",
))
async def create_webhook(
    body: CreateWebhookRequest,
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> WebhookSubscriptionResponse:
    subscription, secret = await get_webhook_manager().create_subscription(
        ctx.organization_id,
        name=body.name,
        url=str(body.url),
        events=[event.value for event in body.events],
    )
    return _to_webhook_response(subscription, secret=secret)


@router.patch("/webhooks/{subscription_uuid}", response_model=WebhookSubscriptionResponse)
async def update_webhook(
    subscription_uuid: str,
    body: UpdateWebhookRequest,
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> WebhookSubscriptionResponse:
    updated = await get_webhook_manager().update_subscription(
        ctx.organization_id,
        subscription_uuid,
        name=body.name,
        url=str(body.url) if body.url is not None else None,
        events=[event.value for event in body.events] if body.events else None,
        is_active=body.is_active,
    )
    return _to_webhook_response(updated)


@router.delete("/webhooks/{subscription_uuid}")
async def delete_webhook(
    subscription_uuid: str,
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> dict:
    await get_webhook_manager().delete_subscription(ctx.organization_id, subscription_uuid)
    return {"status": "deleted", "subscription_uuid": subscription_uuid}


@router.post(
    "/webhooks/{subscription_uuid}/test",
    response_model=WebhookDeliveryResponse,
)
async def test_webhook(
    subscription_uuid: str,
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> WebhookDeliveryResponse:
    result = await get_webhook_manager().deliver_test_event(
        ctx.organization_id, subscription_uuid
    )
    return WebhookDeliveryResponse(**result.__dict__)


@router.post(
    "/calls/trigger/{trigger_path}",
    response_model=TriggerCallResponse,
    **sdk_expose(
        method="trigger_voice_call",
        description="Trigger an outbound AI voice call via an API Trigger node.",
    ),
)
async def platform_trigger_call(
    trigger_path: str,
    body: PlatformTriggerCallRequest,
    request: Request,
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> TriggerCallResponse:
    del ctx
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-API-Key header required")
    call_request = TriggerCallRequest(
        phone_number=body.phone_number,
        initial_context=body.initial_context,
        telephony_configuration_id=body.telephony_configuration_id,
    )
    return await _initiate_call(
        trigger_path,
        call_request,
        api_key,
        use_draft=False,
        target_resolver=_resolve_trigger_target,
    )


@router.post(
    "/calls/workflow/{workflow_uuid}",
    response_model=TriggerCallResponse,
    **sdk_expose(
        method="trigger_voice_call_by_workflow",
        description="Trigger an outbound AI voice call by workflow UUID.",
    ),
)
async def platform_trigger_call_by_workflow(
    workflow_uuid: str,
    body: PlatformTriggerCallRequest,
    request: Request,
    ctx: Annotated[PublicApiContext, Depends(get_public_api_context)],
) -> TriggerCallResponse:
    del ctx
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-API-Key header required")
    call_request = TriggerCallRequest(
        phone_number=body.phone_number,
        initial_context=body.initial_context,
        telephony_configuration_id=body.telephony_configuration_id,
    )
    return await _initiate_call(
        workflow_uuid,
        call_request,
        api_key,
        use_draft=False,
        target_resolver=_resolve_workflow_uuid_target,
    )
