from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.constants import VOICE_ANALYTICS_ENABLED
from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.types import VoiceAnalyticsEvent, VoiceAnalyticsEventType

_VOICE_PATH_PREFIXES = (
    "/api/v1/realtime-audio",
    "/api/v1/realtime-voice",
    "/api/v1/voice-analytics",
    "/api/v1/kenyan-intent",
    "/api/v1/call-routing",
    "/api/v1/whatsapp",
    "/api/v1/mpesa",
)


class VoiceAnalyticsMiddleware(BaseHTTPMiddleware):
    """Attach analytics context and record API latency for voice workflow routes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not VOICE_ANALYTICS_ENABLED or not any(
            path.startswith(prefix) for prefix in _VOICE_PATH_PREFIXES
        ):
            return await call_next(request)

        request.state.voice_analytics = {
            "path": path,
            "method": request.method,
            "started_at": time.monotonic(),
        }

        org_id = _extract_org_id(request)
        if org_id:
            request.state.voice_analytics["organization_id"] = org_id

        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = (
                time.monotonic() - request.state.voice_analytics["started_at"]
            ) * 1000.0
            if org_id and not path.startswith("/api/v1/voice-analytics"):
                emitter = get_voice_analytics_emitter()
                emitter.track(
                    VoiceAnalyticsEvent(
                        event_type=VoiceAnalyticsEventType.RESPONSE_LATENCY,
                        organization_id=org_id,
                        value=round(duration_ms, 2),
                        success=status < 500,
                        labels={
                            "source": "http_middleware",
                            "path": _normalize_path(path),
                            "method": request.method,
                            "status": str(status),
                        },
                        properties={"api_latency_ms": round(duration_ms, 2)},
                    )
                )


def _extract_org_id(request: Request) -> int | None:
    query_org = request.query_params.get("organization_id")
    if query_org:
        try:
            return int(query_org)
        except ValueError:
            pass
    header_org = request.headers.get("X-Organization-Id")
    if header_org:
        try:
            return int(header_org)
        except ValueError:
            pass
    state_org = getattr(request.state, "organization_id", None)
    if state_org is not None:
        try:
            return int(state_org)
        except (TypeError, ValueError):
            pass
    return None


def _normalize_path(path: str) -> str:
    parts = path.split("/")
    normalized = []
    for part in parts:
        if len(part) == 32 and all(c in "0123456789abcdef" for c in part):
            normalized.append(":id")
        elif part.isdigit():
            normalized.append(":id")
        else:
            normalized.append(part)
    return "/".join(normalized)
