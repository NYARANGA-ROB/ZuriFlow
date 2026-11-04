"""Latency benchmarking for load test callers."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CallerMetrics:
    caller_id: str
    connected: bool = False
    connect_ms: float | None = None
    handshake_ms: float | None = None
    first_outbound_ms: float | None = None
    chunks_sent: int = 0
    outbound_chunks: int = 0
    outbound_bytes: int = 0
    ws_rtt_samples: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    def duration_s(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)


@dataclass
class LatencyBenchmark:
    """Aggregates per-caller latency samples across a load test run."""

    _callers: dict[str, CallerMetrics] = field(default_factory=dict)
    _session_start: float = field(default_factory=time.monotonic)

    def caller_metrics(self, caller_id: str) -> CallerMetrics:
        if caller_id not in self._callers:
            self._callers[caller_id] = CallerMetrics(caller_id=caller_id)
        return self._callers[caller_id]

    def record_connect_failure(self, caller_id: str) -> None:
        m = self.caller_metrics(caller_id)
        m.connected = False
        m.ended_at = time.time()

    def record_connect_ms(self, caller_id: str, ms: float) -> None:
        m = self.caller_metrics(caller_id)
        m.connected = True
        m.connect_ms = ms

    def record_handshake_ms(self, caller_id: str, ms: float) -> None:
        self.caller_metrics(caller_id).handshake_ms = ms

    def record_chunk_sent(self, caller_id: str) -> None:
        self.caller_metrics(caller_id).chunks_sent += 1

    def record_sender_done(self, caller_id: str, chunks: int) -> None:
        self.caller_metrics(caller_id).chunks_sent = chunks

    def record_outbound_audio(self, caller_id: str, nbytes: int, seq: int) -> None:
        m = self.caller_metrics(caller_id)
        m.outbound_chunks += 1
        m.outbound_bytes += nbytes
        if m.first_outbound_ms is None:
            m.first_outbound_ms = (time.monotonic() - self._session_start) * 1000.0

    def record_ws_rtt(self, caller_id: str, rtt_ms: float) -> None:
        self.caller_metrics(caller_id).ws_rtt_samples.append(rtt_ms)

    def finalize_caller(self, caller_id: str, *, errors: list[str]) -> None:
        m = self.caller_metrics(caller_id)
        m.errors.extend(errors)
        m.ended_at = time.time()

    def all_callers(self) -> list[CallerMetrics]:
        return list(self._callers.values())

    def aggregate(self) -> dict[str, Any]:
        callers = self.all_callers()
        connected = [c for c in callers if c.connected]
        failed = [c for c in callers if not c.connected]

        def _percentiles(values: list[float]) -> dict[str, float | None]:
            if not values:
                return {"p50": None, "p95": None, "p99": None, "min": None, "max": None, "mean": None}
            ordered = sorted(values)
            return {
                "min": ordered[0],
                "max": ordered[-1],
                "mean": statistics.mean(ordered),
                "p50": _pct(ordered, 50),
                "p95": _pct(ordered, 95),
                "p99": _pct(ordered, 99),
            }

        connect_ms = [c.connect_ms for c in connected if c.connect_ms is not None]
        handshake_ms = [c.handshake_ms for c in connected if c.handshake_ms is not None]
        first_outbound = [c.first_outbound_ms for c in connected if c.first_outbound_ms is not None]
        all_rtt = [r for c in connected for r in c.ws_rtt_samples]

        return {
            "total_callers": len(callers),
            "connected": len(connected),
            "failed": len(failed),
            "success_rate": len(connected) / len(callers) if callers else 0.0,
            "total_chunks_sent": sum(c.chunks_sent for c in connected),
            "total_outbound_bytes": sum(c.outbound_bytes for c in connected),
            "connect_ms": _percentiles(connect_ms),
            "handshake_ms": _percentiles(handshake_ms),
            "first_outbound_ms": _percentiles(first_outbound),
            "ws_rtt_ms": _percentiles(all_rtt),
            "errors": sum(len(c.errors) for c in callers),
        }


def _pct(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)
