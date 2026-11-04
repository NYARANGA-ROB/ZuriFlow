from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StressScenario(str, Enum):
    CONCURRENT_CALLS = "concurrent_calls"
    STK_PUSH_SPIKE = "stk_push_spike"
    WHATSAPP_SPIKE = "whatsapp_spike"
    WEBSOCKET_STABILITY = "websocket_stability"
    INTERRUPTION_BURST = "interruption_burst"
    RETRY_RECOVERY = "retry_recovery"


@dataclass
class OperationResult:
    name: str
    success: bool
    latency_ms: float
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    scenario: StressScenario
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    def record(self, result: OperationResult) -> None:
        self.total += 1
        if result.success:
            self.succeeded += 1
        else:
            self.failed += 1
            if result.error:
                self.errors.append(result.error)
        self.latencies_ms.append(result.latency_ms)

    def finish(self) -> None:
        self.ended_at = time.time()

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total if self.total else 0.0

    @property
    def duration_s(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.value,
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 4),
            "duration_s": round(self.duration_s, 3),
            "latency_ms": _percentiles(self.latencies_ms),
            "errors_sample": self.errors[:20],
            "metadata": dict(self.metadata),
        }


@dataclass
class ReliabilityReport:
    scenarios: list[ScenarioResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def add(self, result: ScenarioResult) -> None:
        self.scenarios.append(result)

    def finish(self) -> None:
        self.ended_at = time.time()

    @property
    def overall_success_rate(self) -> float:
        total = sum(s.total for s in self.scenarios)
        ok = sum(s.succeeded for s in self.scenarios)
        return ok / total if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_s": round((self.ended_at or time.time()) - self.started_at, 2),
            "overall_success_rate": round(self.overall_success_rate, 4),
            "config": dict(self.config),
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


def _percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "p95": None, "p99": None, "max": None, "mean": None}
    ordered = sorted(values)

    def pct(p: float) -> float:
        k = (len(ordered) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(ordered) - 1)
        if f == c:
            return ordered[f]
        return ordered[f] + (ordered[c] - ordered[f]) * (k - f)

    return {
        "min": round(ordered[0], 2),
        "max": round(ordered[-1], 2),
        "mean": round(statistics.mean(ordered), 2),
        "p50": round(pct(50), 2),
        "p95": round(pct(95), 2),
        "p99": round(pct(99), 2),
    }
