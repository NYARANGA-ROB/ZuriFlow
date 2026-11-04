#!/usr/bin/env python3
"""CLI for full AI call workflow reliability testing."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.services.reliability_testing.runner import WorkflowReliabilityRunner


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI call workflow reliability test")
    p.add_argument("--concurrent-calls", type=int, default=20)
    p.add_argument("--stk-spike", type=int, default=50)
    p.add_argument("--whatsapp-spike", type=int, default=80)
    p.add_argument("--interruption-burst", type=int, default=30)
    p.add_argument("--retry-ops", type=int, default=40)
    p.add_argument("--report-dir", default="reliability_reports")
    p.add_argument("--live-ws-url", default=None, help="Live WebSocket URL (optional)")
    return p.parse_args()


async def _main() -> int:
    args = _parse_args()
    runner = WorkflowReliabilityRunner(
        concurrent_calls=args.concurrent_calls,
        stk_spike_size=args.stk_spike,
        whatsapp_spike_size=args.whatsapp_spike,
        interruption_burst=args.interruption_burst,
        retry_operations=args.retry_ops,
        report_dir=args.report_dir,
        live_websocket_url=args.live_ws_url,
        skip_live_websocket=args.live_ws_url is None,
    )
    report, json_path, html_path = await runner.run_and_write()
    print(f"\nReports:\n  {json_path}\n  {html_path}")
    return 0 if report.overall_success_rate >= 0.85 else 1


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
