"""Observability routes: Prometheus scrape, health probes, dashboard metadata."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from api.constants import APP_NAME
from api.services.auth.depends import get_user
from api.services.realtime_observability.health import HEALTH_SERVICE
from api.services.realtime_observability.metrics import REGISTRY
from api.services.realtime_observability.middleware import get_middleware_registry

router = APIRouter(prefix="/realtime-observability", tags=["realtime-observability"])

_DASHBOARD_PATH = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "realtime_observability"
    / "dashboards"
    / "realtime_voice.json"
)


class HealthResponse(BaseModel):
    status: str
    checks: dict
    timestamp: float


class DashboardInfo(BaseModel):
    name: str
    description: str
    grafana_import_path: str
    panels: list[str]


async def _require_metrics_access(
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    expected = os.getenv("METRICS_SCRAPE_TOKEN", "")
    if expected:
        if x_metrics_token != expected:
            raise HTTPException(status_code=403, detail="Invalid metrics token")
        return
    await get_user(authorization, x_api_key)


@router.get("/metrics")
async def prometheus_metrics(
    _: None = Depends(_require_metrics_access),
) -> Response:
    """Prometheus scrape endpoint for realtime voice metrics."""
    body = REGISTRY.generate_latest() + get_middleware_registry().generate_latest()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/health", response_model=HealthResponse)
async def health_detailed() -> HealthResponse:
    status = await HEALTH_SERVICE.detailed()
    return HealthResponse(
        status=status.status, checks=status.checks, timestamp=status.timestamp
    )


@router.get("/health/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    status = HEALTH_SERVICE.liveness()
    return HealthResponse(
        status=status.status, checks=status.checks, timestamp=status.timestamp
    )


@router.get("/health/ready", response_model=HealthResponse)
async def health_ready() -> HealthResponse:
    status = await HEALTH_SERVICE.readiness()
    return HealthResponse(
        status=status.status, checks=status.checks, timestamp=status.timestamp
    )


@router.get("/dashboards/realtime-voice", response_model=DashboardInfo)
async def dashboard_info(_user=Depends(get_user)) -> DashboardInfo:
    """Metadata for importing the bundled Grafana dashboard."""
    return DashboardInfo(
        name=f"{APP_NAME} Realtime Voice",
        description="Latency, interruptions, reconnects, and session health",
        grafana_import_path="api/services/realtime_observability/dashboards/realtime_voice.json",
        panels=[
            "End-to-end latency (p50/p95)",
            "STT / LLM / TTS stage latency",
            "WebSocket round-trip",
            "Interruption rate",
            "Reconnect rate",
            "Active sessions",
        ],
    )


@router.get("/dashboards/realtime-voice/json")
async def dashboard_json(_user=Depends(get_user)) -> Response:
    """Serve Grafana dashboard JSON for import."""
    if not _DASHBOARD_PATH.is_file():
        return Response(content="{}", media_type="application/json", status_code=404)
    return Response(
        content=_DASHBOARD_PATH.read_text(encoding="utf-8"),
        media_type="application/json",
    )


@router.get("/inference-routing")
async def inference_routing(_user=Depends(get_user)) -> dict:
    """On-prem local inference endpoint map (LLM/STT/TTS cluster DNS)."""
    from api.services.local_inference.router import get_local_inference_router

    return get_local_inference_router().summary()


@router.get("/slo")
async def latency_slos(_user=Depends(get_user)) -> dict:
    """Current p50/p95/p99 vs internal conversational latency targets."""
    from api.services.realtime_observability.slo import evaluate_slos

    return evaluate_slos()


@router.get("/bottlenecks")
async def production_bottlenecks(_user=Depends(get_user)) -> dict:
    """Kenya production bottleneck audit + circuit breaker state."""
    from api.services.kenya_production.bottleneck_audit import get_bottleneck_audit
    from api.services.kenya_production.resilience import daraja_circuit, whatsapp_circuit
    from api.services.realtime_observability.metrics import EXTERNAL_API_CIRCUIT_OPEN

    daraja = daraja_circuit().state()
    whatsapp = whatsapp_circuit().state()
    EXTERNAL_API_CIRCUIT_OPEN.labels(service="daraja").set(1 if daraja["open"] else 0)
    EXTERNAL_API_CIRCUIT_OPEN.labels(service="whatsapp").set(1 if whatsapp["open"] else 0)

    return {
        "bottlenecks": get_bottleneck_audit().summary(),
        "circuits": {
            "daraja": daraja,
            "whatsapp": whatsapp,
        },
    }
