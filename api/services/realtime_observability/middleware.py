"""FastAPI middleware for realtime voice HTTP/WebSocket observability."""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.services.realtime_observability.logging import log_event
from api.services.realtime_observability.prometheus_registry import Counter, Histogram, PrometheusRegistry

_MIDDLEWARE_REGISTRY = PrometheusRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "dograh_realtime_http_requests_total",
    "HTTP requests to realtime observability endpoints",
    labelnames=("method", "path", "status"),
    registry=_MIDDLEWARE_REGISTRY,
)
HTTP_REQUEST_DURATION_MS = Histogram(
    "dograh_realtime_http_request_duration_ms",
    "HTTP request duration for realtime routes",
    labelnames=("method", "path"),
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
    registry=_MIDDLEWARE_REGISTRY,
)

_REALTIME_PATH_PREFIXES = (
    "/api/v1/realtime-audio",
    "/api/v1/realtime-voice",
    "/api/v1/realtime-observability",
)


class RealtimeObservabilityMiddleware(BaseHTTPMiddleware):
    """Records request latency and structured logs for realtime voice routes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in _REALTIME_PATH_PREFIXES):
            return await call_next(request)

        start = time.monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            route_path = _normalize_path(path)
            HTTP_REQUESTS_TOTAL.inc(
                method=request.method, path=route_path, status=str(status)
            )
            HTTP_REQUEST_DURATION_MS.observe(
                duration_ms, method=request.method, path=route_path
            )
            log_event(
                "http.request",
                method=request.method,
                path=route_path,
                status=status,
                duration_ms=round(duration_ms, 2),
            )


def _normalize_path(path: str) -> str:
    """Collapse dynamic segments for lower metric cardinality."""
    parts = path.split("/")
    normalized = []
    for part in parts:
        if len(part) == 32 and all(c in "0123456789abcdef" for c in part):
            normalized.append(":session_id")
        else:
            normalized.append(part)
    return "/".join(normalized)


def get_middleware_registry() -> PrometheusRegistry:
    return _MIDDLEWARE_REGISTRY
