"""Load test orchestrator."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from scripts.load_test.realtime_voice.benchmark import LatencyBenchmark
from scripts.load_test.realtime_voice.caller import ConcurrentCallerPool
from scripts.load_test.realtime_voice.config import LoadTestConfig
from scripts.load_test.realtime_voice.memory import MemoryMonitor
from scripts.load_test.realtime_voice.reports import PerformanceReport


@dataclass
class LoadTestRunner:
    """Runs concurrent caller simulation with benchmarking and memory checks."""

    config: LoadTestConfig
    benchmark: LatencyBenchmark = field(default_factory=LatencyBenchmark)
    memory: MemoryMonitor = field(default_factory=MemoryMonitor)
    _memory_task: asyncio.Task | None = field(default=None, init=False)

    async def run(self) -> PerformanceReport:
        self.memory = MemoryMonitor(
            growth_threshold_mb=self.config.memory_growth_threshold_mb
        )
        self.memory.start()
        self._memory_task = asyncio.create_task(self._memory_poll_loop())

        pool = ConcurrentCallerPool(config=self.config, benchmark=self.benchmark)
        started = time.time()
        try:
            callers = await pool.run()
        finally:
            if self._memory_task:
                self._memory_task.cancel()
                await asyncio.gather(self._memory_task, return_exceptions=True)
            self.memory.stop()

        report = PerformanceReport(
            config=self.config,
            benchmark=self.benchmark,
            memory_analysis=self.memory.analyze(),
            callers=callers,
            started_at=started,
            ended_at=time.time(),
        )
        return report

    async def _memory_poll_loop(self) -> None:
        interval = self.config.memory_check_interval_s
        while True:
            await asyncio.sleep(interval)
            self.memory.snapshot(f"poll_{int(time.time())}")
