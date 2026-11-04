"""Performance report generation (JSON + HTML)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.load_test.realtime_voice.benchmark import CallerMetrics, LatencyBenchmark
from scripts.load_test.realtime_voice.config import LoadTestConfig


@dataclass
class PerformanceReport:
    """Builds and writes load test performance reports."""

    config: LoadTestConfig
    benchmark: LatencyBenchmark
    memory_analysis: dict[str, Any] = field(default_factory=dict)
    callers: list[CallerMetrics] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    def build_summary(self) -> dict[str, Any]:
        agg = self.benchmark.aggregate()
        duration = (self.ended_at or time.time()) - self.started_at
        return {
            "report_version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_s": round(duration, 2),
            "config": {
                "url": self.config.websocket_url(),
                "endpoint": self.config.endpoint.value,
                "concurrent_callers": self.config.concurrent_callers,
                "ramp_up_s": self.config.ramp_up_s,
                "duration_s": self.config.duration_s,
                "chunk_ms": self.config.chunk_ms,
                "speech_pattern": self.config.speech_pattern,
            },
            "summary": agg,
            "memory": self.memory_analysis,
            "callers": [
                {
                    "caller_id": c.caller_id,
                    "connected": c.connected,
                    "connect_ms": c.connect_ms,
                    "handshake_ms": c.handshake_ms,
                    "first_outbound_ms": c.first_outbound_ms,
                    "chunks_sent": c.chunks_sent,
                    "outbound_chunks": c.outbound_chunks,
                    "outbound_bytes": c.outbound_bytes,
                    "ws_rtt_mean": (
                        round(sum(c.ws_rtt_samples) / len(c.ws_rtt_samples), 2)
                        if c.ws_rtt_samples
                        else None
                    ),
                    "errors": c.errors,
                }
                for c in self.callers
            ],
        }

    def write(self, report_dir: str | None = None) -> tuple[Path, Path]:
        out_dir = Path(report_dir or self.config.report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        prefix = self.config.report_prefix

        json_path = out_dir / f"{prefix}_{ts}.json"
        html_path = out_dir / f"{prefix}_{ts}.html"

        summary = self.build_summary()
        json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        html_path.write_text(self._render_html(summary), encoding="utf-8")
        return json_path, html_path

    def print_console(self) -> None:
        s = self.build_summary()["summary"]
        print("\n=== Realtime Voice Load Test Results ===")
        print(f"URL:          {self.config.websocket_url()}")
        print(f"Callers:      {s['total_callers']} ({s['connected']} ok, {s['failed']} failed)")
        print(f"Success rate: {s['success_rate'] * 100:.1f}%")
        print(f"Chunks sent:  {s['total_chunks_sent']}")
        print(f"Outbound:     {s['total_outbound_bytes']} bytes")
        for key in ("connect_ms", "handshake_ms", "first_outbound_ms", "ws_rtt_ms"):
            stats = s.get(key, {})
            if stats.get("mean") is not None:
                print(
                    f"{key:20s} mean={stats['mean']:.1f}ms  "
                    f"p50={stats['p50']:.1f}  p95={stats['p95']:.1f}  p99={stats['p99']:.1f}"
                )
        mem = self.memory_analysis
        if mem:
            print(f"Memory RSS growth: {mem.get('rss_growth_mb')} MB")
            print(f"Leak suspected:    {mem.get('leak_suspected')}")

    def _render_html(self, summary: dict[str, Any]) -> str:
        s = summary["summary"]
        rows = ""
        for key in ("connect_ms", "handshake_ms", "first_outbound_ms", "ws_rtt_ms"):
            stats = s.get(key, {})
            rows += f"""
            <tr>
              <td>{key}</td>
              <td>{_fmt(stats.get('min'))}</td>
              <td>{_fmt(stats.get('p50'))}</td>
              <td>{_fmt(stats.get('p95'))}</td>
              <td>{_fmt(stats.get('p99'))}</td>
              <td>{_fmt(stats.get('max'))}</td>
              <td>{_fmt(stats.get('mean'))}</td>
            </tr>"""

        mem = summary.get("memory", {})
        leak = mem.get("leak_suspected", False)
        leak_class = "bad" if leak else "ok"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Realtime Voice Load Test — {summary['generated_at']}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
    h1 {{ font-size: 1.4rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; width: 100%; max-width: 900px; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f5f5f5; }}
    .ok {{ color: #0a7; font-weight: 600; }}
    .bad {{ color: #c33; font-weight: 600; }}
    .meta {{ color: #555; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Realtime Voice Load Test Report</h1>
  <p class="meta">Generated {summary['generated_at']} · Duration {summary['duration_s']}s</p>
  <p><strong>URL:</strong> {summary['config']['url']}</p>
  <p>
    <strong>Callers:</strong> {s['total_callers']}
    &nbsp;|&nbsp; <strong>Connected:</strong> {s['connected']}
    &nbsp;|&nbsp; <strong>Failed:</strong> {s['failed']}
    &nbsp;|&nbsp; <strong>Success:</strong> {s['success_rate'] * 100:.1f}%
  </p>
  <p>
    <strong>Chunks sent:</strong> {s['total_chunks_sent']}
    &nbsp;|&nbsp; <strong>Outbound bytes:</strong> {s['total_outbound_bytes']}
    &nbsp;|&nbsp; <strong>Errors:</strong> {s['errors']}
  </p>
  <h2>Latency percentiles (ms)</h2>
  <table>
    <tr><th>Metric</th><th>Min</th><th>p50</th><th>p95</th><th>p99</th><th>Max</th><th>Mean</th></tr>
    {rows}
  </table>
  <h2>Memory</h2>
  <p class="{leak_class}">Leak suspected: {leak}</p>
  <p>RSS growth: {_fmt(mem.get('rss_growth_mb'))} MB ·
     Tracemalloc growth: {_fmt(mem.get('tracemalloc_mb_growth_mb') or mem.get('tracemalloc_growth_mb'))} MB</p>
</body>
</html>"""


def _fmt(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.1f}"
    return str(val)
