"""Rolling p50/p95/p99 samples for realtime pipeline stages. No tenant payloads."""

from __future__ import annotations

import math
import threading
from collections import defaultdict, deque

_MAX = 2000
_lock = threading.Lock()
_samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_MAX))


def record_stage_ms(stage: str, value_ms: float) -> None:
    if value_ms < 0:
        return
    with _lock:
        _samples[stage].append(float(value_ms))


def percentiles(stage: str) -> dict[str, float | int | None]:
    with _lock:
        values = list(_samples.get(stage, ()))
    return _pct(values)


def snapshot() -> dict[str, dict[str, float | int | None]]:
    with _lock:
        stages = {k: list(v) for k, v in _samples.items()}
    return {k: _pct(v) for k, v in stages.items()}


def reset_for_tests() -> None:
    with _lock:
        _samples.clear()


def _pct(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p50": None, "p95": None, "p99": None, "max": None}
    ordered = sorted(values)
    n = len(ordered)

    def at(p: float) -> float:
        idx = min(n - 1, max(0, math.ceil(p / 100.0 * n) - 1))
        return round(ordered[idx], 2)

    return {
        "count": n,
        "p50": at(50),
        "p95": at(95),
        "p99": at(99),
        "max": round(ordered[-1], 2),
    }
