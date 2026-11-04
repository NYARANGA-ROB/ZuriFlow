"""Global HTTP request metrics for production observability."""

from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.constants import ENVIRONMENT
from api.enums import Environment

try:
    from prometheus_client import Counter, Histogram

    HTTP_REQUESTS = Counter(
        "dograh_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    HTTP_LATENCY = Histogram(
        "dograh_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )
    _METRICS_ENABLED = True
except ImportError:
    _METRICS_ENABLED = False


def _normalize_path(path: str) -> str:
    parts = []
    for segment in path.split("/"):
        if segment.isdigit() or (len(segment) == 32 and segment.isalnum()):
            parts.append(":id")
        else:
            parts.append(segment)
    return "/".join(parts)


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts and latency for all /api/v1 routes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not _METRICS_ENABLED or not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        started = time.monotonic()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.monotonic() - started
            path = _normalize_path(request.url.path)
            method = request.method
            HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
            HTTP_LATENCY.labels(method=method, path=path).observe(elapsed)
