from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from api.services.reliability_testing.types import OperationResult, ScenarioResult, StressScenario


@dataclass
class WebSocketStabilityProbe:
    """Measure WebSocket stability metrics from a live or simulated session."""

    reconnect_attempts: int = 3
    ping_interval_s: float = 2.0
    session_duration_s: float = 10.0

    disconnects: int = 0
    reconnects: int = 0
    ping_failures: int = 0
    messages_received: int = 0
    _errors: list[str] = field(default_factory=list)

    async def run_simulated(self) -> ScenarioResult:
        """Offline stability model — no live server required."""
        result = ScenarioResult(scenario=StressScenario.WEBSOCKET_STABILITY)
        start = time.perf_counter()

        for cycle in range(self.reconnect_attempts + 1):
            cycle_start = time.perf_counter()
            try:
                await self._simulate_session()
                op = OperationResult(
                    name=f"cycle-{cycle}",
                    success=True,
                    latency_ms=(time.perf_counter() - cycle_start) * 1000.0,
                    metadata={"reconnect": cycle > 0},
                )
                result.record(op)
            except Exception as exc:
                self._errors.append(str(exc))
                op = OperationResult(
                    name=f"cycle-{cycle}",
                    success=False,
                    latency_ms=(time.perf_counter() - cycle_start) * 1000.0,
                    error=str(exc),
                )
                result.record(op)
            if cycle < self.reconnect_attempts:
                self.disconnects += 1
                await asyncio.sleep(0.05)
                self.reconnects += 1

        result.metadata = {
            "disconnects": self.disconnects,
            "reconnects": self.reconnects,
            "ping_failures": self.ping_failures,
            "messages_received": self.messages_received,
            "total_duration_ms": (time.perf_counter() - start) * 1000.0,
        }
        result.finish()
        return result

    async def run_live(self, websocket_url: str) -> ScenarioResult:
        """Probe a live WebSocket endpoint (requires running API)."""
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("websockets package required for live probe") from exc

        result = ScenarioResult(scenario=StressScenario.WEBSOCKET_STABILITY)
        for cycle in range(self.reconnect_attempts + 1):
            cycle_start = time.perf_counter()
            try:
                async with websockets.connect(websocket_url, open_timeout=10.0) as ws:
                    await ws.send('{"type":"hello","sample_rate":16000,"channels":1}')
                    raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    self.messages_received += 1
                    deadline = time.monotonic() + self.session_duration_s
                    while time.monotonic() < deadline:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=self.ping_interval_s)
                            if msg:
                                self.messages_received += 1
                        except asyncio.TimeoutError:
                            await ws.send('{"type":"ping","ts":%s}' % time.time())
                op = OperationResult(
                    name=f"live-cycle-{cycle}",
                    success=True,
                    latency_ms=(time.perf_counter() - cycle_start) * 1000.0,
                )
                result.record(op)
            except Exception as exc:
                op = OperationResult(
                    name=f"live-cycle-{cycle}",
                    success=False,
                    latency_ms=(time.perf_counter() - cycle_start) * 1000.0,
                    error=str(exc),
                )
                result.record(op)
        result.metadata = {
            "url": websocket_url,
            "messages_received": self.messages_received,
        }
        result.finish()
        return result

    async def _simulate_session(self) -> None:
        deadline = time.monotonic() + self.session_duration_s
        pings = 0
        while time.monotonic() < deadline:
            await asyncio.sleep(self.ping_interval_s)
            pings += 1
            if pings % 7 == 0:
                self.ping_failures += 1
                raise ConnectionError("simulated websocket drop")
            self.messages_received += 1
