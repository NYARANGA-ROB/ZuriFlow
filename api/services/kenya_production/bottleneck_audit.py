from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from api.constants import KENYA_PRODUCTION_MODE


@dataclass(frozen=True)
class BottleneckAudit:
    """Collect hot-path timing samples for production tuning."""

    samples: dict[str, list[float]] = field(default_factory=dict)

    def record(self, stage: str, duration_ms: float) -> None:
        bucket = self.samples.setdefault(stage, [])
        bucket.append(duration_ms)
        if len(bucket) > 500:
            del bucket[: len(bucket) - 500]

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for stage, values in self.samples.items():
            if not values:
                continue
            ordered = sorted(values)
            out[stage] = {
                "count": len(ordered),
                "p50_ms": ordered[len(ordered) // 2],
                "p95_ms": ordered[int(len(ordered) * 0.95)],
                "max_ms": ordered[-1],
            }
        return out


_audit = BottleneckAudit()


def get_bottleneck_audit() -> BottleneckAudit:
    return _audit


class StageTimer:
    """Context manager for bottleneck audit spans."""

    def __init__(self, stage: str) -> None:
        self._stage = stage
        self._start = 0.0

    def __enter__(self) -> StageTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        ms = (time.perf_counter() - self._start) * 1000.0
        if KENYA_PRODUCTION_MODE:
            _audit.record(self._stage, ms)
        from api.services.realtime_observability.metrics import INTENT_MS, NORMALIZE_MS
        from api.services.realtime_observability.percentiles import record_stage_ms

        record_stage_ms(self._stage, ms)
        if self._stage == "normalize":
            NORMALIZE_MS.observe(ms)
        elif self._stage == "intent":
            INTENT_MS.observe(ms)
