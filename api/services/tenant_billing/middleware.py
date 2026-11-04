"""Subscription enforcement middleware for billable API routes."""

from __future__ import annotations

from typing import Callable

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.services.tenant_billing.plan import get_subscription_status
from api.services.tenant_billing.types import SUSPENDED_SUBSCRIPTION_STATUSES

_API_PREFIX = "/api/v1"
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/auth/",
    "/api/v1/public/",
    "/api/v1/mcp",
    "/api/v1/tenant-billing/",
    "/api/v1/tenant/billing/",
    "/api/v1/organizations/",
    "/api/v1/realtime-observability/",
)
_BILLABLE_PREFIXES = (
    "/api/v1/telephony/",
    "/api/v1/campaign/",
    "/api/v1/voice-campaign/",
    "/api/v1/whatsapp/",
    "/api/v1/agent-stream/",
    "/api/v1/realtime-voice/",
    "/api/v1/realtime-audio/",
    "/api/v1/platform/",
)


class TenantSubscriptionMiddleware(BaseHTTPMiddleware):
    """Block billable routes when tenant subscription is suspended or past due."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not TENANT_USAGE_BILLING_ENABLED:
            return await call_next(request)

        path = request.url.path
        if not path.startswith(_API_PREFIX) or _is_exempt(path):
            return await call_next(request)
        if not _is_billable(path):
            return await call_next(request)

        org_id = _resolve_organization_id(request)
        if org_id is None:
            return await call_next(request)

        status = await get_subscription_status(org_id)
        if status in SUSPENDED_SUBSCRIPTION_STATUSES:
            return JSONResponse(
                status_code=402,
                content={
                    "detail": "Subscription inactive. Update billing to continue.",
                    "subscription_status": status,
                },
            )

        return await call_next(request)


def _is_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


def _is_billable(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _BILLABLE_PREFIXES)


def _resolve_organization_id(request: Request) -> int | None:
    ctx = getattr(request.state, "public_api_context", None)
    if ctx is not None:
        return int(ctx.organization_id)

    tenant_ctx = getattr(request.state, "tenant_context", None)
    if tenant_ctx is not None:
        return int(tenant_ctx.organization_id)

    header_org = request.headers.get("X-Organization-Id")
    if header_org:
        try:
            return int(header_org)
        except ValueError:
            return None
    return None
