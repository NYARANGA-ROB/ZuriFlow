"""Concurrent caller pool for WebSocket stress testing."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from scripts.load_test.realtime_voice.benchmark import CallerMetrics, LatencyBenchmark
from scripts.load_test.realtime_voice.config import LoadTestConfig
from scripts.load_test.realtime_voice.websocket_simulator import WebSocketSimulator


@dataclass
class ConcurrentCallerPool:
    """Spawns and supervises N concurrent WebSocket caller simulators."""

    config: LoadTestConfig
    benchmark: LatencyBenchmark = field(default_factory=LatencyBenchmark)
    _tasks: list[asyncio.Task] = field(default_factory=list, init=False)

    async def run(self) -> list[CallerMetrics]:
        n = self.config.concurrent_callers
        interval = self.config.spawn_interval_s
        if interval <= 0 and self.config.ramp_up_s > 0 and n > 1:
            interval = self.config.ramp_up_s / n
        elif interval <= 0:
            interval = 0.05

        async def _spawn_one(idx: int) -> CallerMetrics:
            if idx > 0 and interval > 0:
                await asyncio.sleep(idx * interval)
            sim = WebSocketSimulator(
                config=self.config,
                caller_id=f"c{idx:04d}",
                benchmark=self.benchmark,
            )
            return await sim.run(self.config.duration_s)

        self._tasks = [
            asyncio.create_task(_spawn_one(i), name=f"caller-{i}")
            for i in range(n)
        ]

        raw = await asyncio.gather(*self._tasks, return_exceptions=True)
        results: list[CallerMetrics] = []
        for item in raw:
            if isinstance(item, BaseException):
                continue
            results.append(item)
        return results

    async def cancel(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    @property
    def peak_concurrency(self) -> int:
        return self.config.concurrent_callers

    def spawn_rate_per_s(self) -> float:
        if self.config.ramp_up_s <= 0:
            return float(self.config.concurrent_callers)
        return self.config.concurrent_callers / self.config.ramp_up_s
