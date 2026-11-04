"""Generate JSON and HTML reliability reports."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from api.services.reliability_testing.types import ReliabilityReport, ScenarioResult


class ReliabilityReportWriter:
    def __init__(self, report: ReliabilityReport, *, report_dir: str = "reliability_reports") -> None:
        self._report = report
        self._report_dir = report_dir

    def write(self, *, prefix: str = "workflow_reliability") -> tuple[Path, Path]:
        out_dir = Path(self._report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"{prefix}_{ts}.json"
        html_path = out_dir / f"{prefix}_{ts}.html"
        data = self._report.to_dict()
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        html_path.write_text(self._render_html(data), encoding="utf-8")
        return json_path, html_path

    def print_console(self) -> None:
        data = self._report.to_dict()
        print("\n=== AI Call Workflow Reliability Report ===")
        print(f"Duration:       {data['duration_s']}s")
        print(f"Overall success: {data['overall_success_rate'] * 100:.1f}%")
        for scenario in data["scenarios"]:
            print(
                f"  {scenario['scenario']:22s} "
                f"{scenario['succeeded']:4d}/{scenario['total']:4d} "
                f"({scenario['success_rate'] * 100:5.1f}%) "
                f"p95={_fmt_lat(scenario, 'p95')}ms"
            )

    def _render_html(self, data: dict[str, Any]) -> str:
        rows = ""
        for s in data["scenarios"]:
            lat = s.get("latency_ms", {})
            rows += f"""
            <tr>
              <td>{s['scenario']}</td>
              <td>{s['succeeded']}/{s['total']}</td>
              <td>{s['success_rate'] * 100:.1f}%</td>
              <td>{_fmt(lat.get('p50'))}</td>
              <td>{_fmt(lat.get('p95'))}</td>
              <td>{_fmt(lat.get('p99'))}</td>
              <td>{s['duration_s']:.2f}s</td>
            </tr>"""

        passed = data["overall_success_rate"] >= 0.9
        status_class = "ok" if passed else "bad"
        status_text = "PASS" if passed else "NEEDS ATTENTION"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Workflow Reliability — {data['generated_at']}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 960px; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f5f5f5; }}
    .ok {{ color: #0a7; font-weight: 700; }}
    .bad {{ color: #c33; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>AI Call Workflow Reliability Report</h1>
  <p>Generated {data['generated_at']} · Duration {data['duration_s']}s</p>
  <p class="{status_class}">Status: {status_text} · Overall success {data['overall_success_rate'] * 100:.1f}%</p>
  <h2>Scenarios</h2>
  <table>
    <tr>
      <th>Scenario</th><th>OK/Total</th><th>Rate</th>
      <th>p50 ms</th><th>p95 ms</th><th>p99 ms</th><th>Duration</th>
    </tr>
    {rows}
  </table>
</body>
</html>"""


def _fmt(val: Any) -> str:
    if val is None:
        return "—"
    return f"{val:.1f}"


def _fmt_lat(scenario: dict[str, Any], key: str) -> str:
    lat = scenario.get("latency_ms", {})
    v = lat.get(key)
    return "—" if v is None else f"{v:.0f}"
