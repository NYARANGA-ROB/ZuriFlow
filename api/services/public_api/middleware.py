"""Public API gateway middleware: auth, rate limits, and usage tracking."""

from __future__ import annotations

import time
from typing import Callable

from fastapi.responses import JSONResponse
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.constants import PUBLIC_API_ENABLED
from api.services.public_api.auth import resolve_public_api_context
from api.services.public_api.rate_limiter import get_public_api_rate_limiter
from api.services.public_api.usage import get_public_api_usage_tracker

_PLATFORM_PREFIX = "/api/v1/platform"
_PUBLIC_AGENT_PREFIX = "/api/v1/public/agent"


class PublicApiGatewayMiddleware(BaseHTTPMiddleware):
    """Authenticate API keys, enforce rate limits, and record usage analytics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not PUBLIC_API_ENABLED or not _is_gateway_path(path):
            return await call_next(request)

        raw_key = request.headers.get("X-API-Key")
        if not raw_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "X-API-Key header required"},
            )

        try:
            ctx = await resolve_public_api_context(raw_key)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        request.state.public_api_context = ctx

        limiter = get_public_api_rate_limiter()
        result = await limiter.check(
            organization_id=ctx.organization_id,
            api_key_id=ctx.api_key_id,
        )
        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "Retry-After": str(int(result.retry_after_s) or 1),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        started = time.monotonic()
        response = await call_next(request)
        latency_ms = (time.monotonic() - started) * 1000.0

        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(result.remaining, 0))

        tracker = get_public_api_usage_tracker()
        await tracker.record(ctx, request, response, latency_ms=latency_ms)
        return response


def _is_gateway_path(path: str) -> bool:
    return path.startswith(_PLATFORM_PREFIX) or path.startswith(_PUBLIC_AGENT_PREFIX)
