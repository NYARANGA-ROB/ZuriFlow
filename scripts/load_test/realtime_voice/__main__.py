#!/usr/bin/env python3
"""CLI entry point for realtime voice load testing.

Usage (from repo root)::

    pip install -r scripts/load_test/requirements.txt
    python scripts/run_realtime_voice_load_test.py --callers 20 --duration 30

    # Stress realtime-voice pipeline (requires API keys on server):
    python scripts/run_realtime_voice_load_test.py \\
        --endpoint realtime_voice --callers 10 --duration 60
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.load_test.realtime_voice.config import EndpointKind, LoadTestConfig
from scripts.load_test.realtime_voice.runner import LoadTestRunner


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Realtime voice WebSocket load test")
    p.add_argument(
        "--url",
        default="ws://localhost:8000",
        help="WebSocket base URL (default: ws://localhost:8000)",
    )
    p.add_argument(
        "--endpoint",
        choices=["realtime_audio", "realtime_voice"],
        default="realtime_audio",
        help="Target endpoint (default: realtime_audio)",
    )
    p.add_argument("--callers", type=int, default=10, help="Concurrent callers")
    p.add_argument("--duration", type=float, default=30.0, help="Call duration seconds")
    p.add_argument("--ramp-up", type=float, default=5.0, help="Ramp-up period seconds")
    p.add_argument("--chunk-ms", type=int, default=20, help="Audio chunk size ms")
    p.add_argument(
        "--pattern",
        choices=["tone", "noise", "silence", "alternating"],
        default="tone",
        help="Synthetic audio pattern",
    )
    p.add_argument("--report-dir", default="load_test_reports", help="Output directory")
    p.add_argument("--no-audio", action="store_true", help="Skip sending audio (connect only)")
    p.add_argument(
        "--memory-threshold-mb",
        type=float,
        default=50.0,
        help="RSS growth threshold for leak warning",
    )
    return p.parse_args()


async def _main() -> int:
    args = _parse_args()
    config = LoadTestConfig(
        base_url=args.url,
        endpoint=EndpointKind(args.endpoint),
        concurrent_callers=args.callers,
        ramp_up_s=args.ramp_up,
        duration_s=args.duration,
        chunk_ms=args.chunk_ms,
        speech_pattern=args.pattern,
        send_audio=not args.no_audio,
        report_dir=args.report_dir,
        memory_growth_threshold_mb=args.memory_threshold_mb,
    )

    print(f"Starting load test: {config.concurrent_callers} callers → {config.websocket_url()}")
    runner = LoadTestRunner(config)
    report = await runner.run()
    report.print_console()
    json_path, html_path = report.write()
    print(f"\nReports written:\n  {json_path}\n  {html_path}")

    if report.build_summary()["summary"]["failed"] > 0:
        return 1
    if report.memory_analysis.get("leak_suspected"):
        return 2
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
