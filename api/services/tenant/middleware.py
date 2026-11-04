"""HTTP middleware for tenant context propagation and isolation headers."""

from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.constants import TENANT_ISOLATION_ENABLED

_TENANT_PATH_PREFIX = "/api/v1"
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/public/",
    "/api/v1/auth/",
    "/api/v1/mcp",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Attach tenant metadata to requests and enforce header consistency hints.

    Full RBAC resolution happens in ``get_tenant_context`` (route dependency) because
    authentication is also dependency-based. This middleware:
    - Parses optional ``X-Organization-Id`` for downstream dependencies
    - Sets ``request.state.tenant_isolation_enabled``
    - Adds ``X-Tenant-Isolation`` response header on tenant routes
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith(_TENANT_PATH_PREFIX) or _is_public_path(path):
            return await call_next(request)

        request.state.tenant_isolation_enabled = TENANT_ISOLATION_ENABLED
        header_org = request.headers.get("X-Organization-Id")
        if header_org:
            try:
                request.state.header_organization_id = int(header_org)
            except ValueError:
                request.state.header_organization_id = None
        else:
            request.state.header_organization_id = None

        response = await call_next(request)

        if TENANT_ISOLATION_ENABLED:
            response.headers["X-Tenant-Isolation"] = "strict"
        else:
            response.headers["X-Tenant-Isolation"] = "disabled"
        return response


def _is_public_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)
