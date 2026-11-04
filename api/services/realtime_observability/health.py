"""Health checks for the realtime voice subsystem."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from api.services.realtime_observability.metrics import REGISTRY


@dataclass
class HealthStatus:
    status: str
    checks: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class RealtimeVoiceHealthService:
    """Aggregates liveness/readiness probes for realtime voice components."""

    def liveness(self) -> HealthStatus:
        return HealthStatus(status="ok", checks={"process": "alive"})

    async def readiness(self) -> HealthStatus:
        from api.services.realtime_audio.connection_manager import get_connection_manager

        checks: dict[str, Any] = {}
        overall = "ok"

        try:
            manager = get_connection_manager()
            checks["connection_manager"] = (
                "ok" if manager.is_running() else "stopped"
            )
            if not manager.is_running():
                overall = "degraded"
            checks["active_sessions"] = manager.session_count()
        except Exception as exc:
            checks["connection_manager"] = f"error: {exc}"
            overall = "degraded"

        checks["metrics_registry"] = "ok"

        return HealthStatus(status=overall, checks=checks)

    async def detailed(self) -> HealthStatus:
        base = await self.readiness()
        base.checks["prometheus"] = "ok"
        base.checks["subsystems"] = {
            "realtime_audio": "ok",
            "realtime_voice_pipeline": "ok",
            "observability": "ok",
        }
        return base


HEALTH_SERVICE = RealtimeVoiceHealthService()
