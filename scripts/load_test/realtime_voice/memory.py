"""Memory usage monitoring for leak detection during load tests."""

from __future__ import annotations

import gc
import tracemalloc
from dataclasses import dataclass, field
from typing import Any


def _rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # Linux: ru_maxrss in KB; macOS: bytes
        import sys

        if sys.platform == "darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except Exception:
        return None


@dataclass
class MemorySnapshot:
    label: str
    rss_mb: float | None
    tracemalloc_mb: float | None
    peak_tracemalloc_mb: float | None


@dataclass
class MemoryMonitor:
    """Tracks RSS and tracemalloc growth across load test phases."""

    growth_threshold_mb: float = 50.0
    _snapshots: list[MemorySnapshot] = field(default_factory=list)
    _tracemalloc_started: bool = False
    _top_allocations: list[dict[str, Any]] = field(default_factory=list)

    def start(self) -> None:
        if not tracemalloc.is_tracing():
            tracemalloc.start(25)
            self._tracemalloc_started = True
        self.snapshot("start")

    def snapshot(self, label: str) -> MemorySnapshot:
        current, peak = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)
        snap = MemorySnapshot(
            label=label,
            rss_mb=_rss_mb(),
            tracemalloc_mb=current / (1024 * 1024),
            peak_tracemalloc_mb=peak / (1024 * 1024),
        )
        self._snapshots.append(snap)
        return snap

    def stop(self) -> None:
        gc.collect()
        self._top_allocations = self._capture_top_allocations()
        self.snapshot("end")
        if self._tracemalloc_started and tracemalloc.is_tracing():
            tracemalloc.stop()

    def analyze(self) -> dict[str, Any]:
        if len(self._snapshots) < 2:
            return {"leak_suspected": False, "snapshots": []}

        start = self._snapshots[0]
        end = self._snapshots[-1]
        rss_growth = None
        if start.rss_mb is not None and end.rss_mb is not None:
            rss_growth = end.rss_mb - start.rss_mb

        trace_growth = None
        if start.tracemalloc_mb is not None and end.tracemalloc_mb is not None:
            trace_growth = end.tracemalloc_mb - start.tracemalloc_mb

        leak_suspected = False
        if rss_growth is not None and rss_growth > self.growth_threshold_mb:
            leak_suspected = True
        if trace_growth is not None and trace_growth > self.growth_threshold_mb / 2:
            leak_suspected = True

        return {
            "leak_suspected": leak_suspected,
            "rss_growth_mb": rss_growth,
            "tracemalloc_growth_mb": trace_growth,
            "threshold_mb": self.growth_threshold_mb,
            "snapshots": [
                {
                    "label": s.label,
                    "rss_mb": round(s.rss_mb, 2) if s.rss_mb else None,
                    "tracemalloc_mb": round(s.tracemalloc_mb, 2) if s.tracemalloc_mb else None,
                }
                for s in self._snapshots
            ],
            "top_allocations": self._top_allocations,
        }

    def _capture_top_allocations(self) -> list[dict[str, Any]]:
        if not tracemalloc.is_tracing():
            return []
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")[:10]
        return [
            {
                "file": str(stat.traceback[0].filename) if stat.traceback else "?",
                "line": stat.traceback[0].lineno if stat.traceback else 0,
                "size_kb": round(stat.size / 1024, 2),
            }
            for stat in stats
        ]
