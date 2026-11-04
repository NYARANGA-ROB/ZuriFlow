from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class ConcurrentSimulator:
    """Run many async workers with optional ramp-up."""

    workers: int
    ramp_up_s: float = 0.0
    per_worker_timeout_s: float = 60.0

    async def run(
        self,
        worker_fn: Callable[[int], Awaitable[T]],
    ) -> list[T | BaseException]:
        interval = self.ramp_up_s / self.workers if self.workers > 1 and self.ramp_up_s > 0 else 0.0

        async def _wrapped(idx: int) -> T:
            if idx > 0 and interval > 0:
                await asyncio.sleep(idx * interval)
            return await asyncio.wait_for(
                worker_fn(idx),
                timeout=self.per_worker_timeout_s,
            )

        tasks = [asyncio.create_task(_wrapped(i), name=f"worker-{i}") for i in range(self.workers)]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def run_collecting(
        self,
        worker_fn: Callable[[int], Awaitable[Any]],
    ) -> dict[str, Any]:
        started = time.monotonic()
        raw = await self.run(worker_fn)
        elapsed = time.monotonic() - started
        successes = sum(1 for r in raw if not isinstance(r, BaseException))
        failures = len(raw) - successes
        errors = [str(r) for r in raw if isinstance(r, BaseException)]
        return {
            "workers": self.workers,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / len(raw) if raw else 0.0,
            "elapsed_s": round(elapsed, 3),
            "throughput_per_s": round(successes / elapsed, 2) if elapsed > 0 else 0.0,
            "errors_sample": errors[:10],
        }
