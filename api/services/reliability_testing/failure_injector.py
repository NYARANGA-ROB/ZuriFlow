from __future__ import annotations

import asyncio
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

from api.services.reliability_testing.concurrent_simulator import ConcurrentSimulator
from api.services.reliability_testing.types import OperationResult, ScenarioResult, StressScenario

T = TypeVar("T")


@dataclass
class FailureInjector:
    """Inject transient failures then verify recovery."""

    fail_rate: float = 0.4
    fail_until_attempt: int = 2
    error_message: str = "injected failure"

    _attempts: dict[str, int] = field(default_factory=dict)

    def wrap(self, key: str, fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def _wrapped(*args: Any, **kwargs: Any) -> T:
            attempt = self._attempts.get(key, 0) + 1
            self._attempts[key] = attempt
            if attempt < self.fail_until_attempt and random.random() < self.fail_rate:
                raise RuntimeError(self.error_message)
            return await fn(*args, **kwargs)

        return _wrapped

    @asynccontextmanager
    async def failing_phase(self):
        original_rate = self.fail_rate
        original_until = self.fail_until_attempt
        self.fail_rate = 1.0
        self.fail_until_attempt = 10**9
        try:
            yield self
        finally:
            self.fail_rate = original_rate
            self.fail_until_attempt = original_until


@dataclass
class RetryRecoverySimulator:
    """Verify operations recover after injected failures."""

    operations: int = 40
    max_attempts: int = 3

    async def run(
        self,
        operation: Callable[[int, int], Awaitable[bool]] | None = None,
    ) -> ScenarioResult:
        result = ScenarioResult(scenario=StressScenario.RETRY_RECOVERY)
        injector = FailureInjector(fail_rate=0.5, fail_until_attempt=2)

        async def _op(idx: int) -> OperationResult:
            start = time.perf_counter()
            attempt = 0
            last_error = ""
            while attempt < self.max_attempts:
                attempt += 1
                try:
                    if operation is None:
                        wrapped = injector.wrap(f"op-{idx}", _default_operation)
                        ok = await wrapped(idx)
                    else:
                        ok = await operation(idx, attempt)
                    op = OperationResult(
                        name=f"retry-{idx}",
                        success=bool(ok),
                        latency_ms=(time.perf_counter() - start) * 1000.0,
                        metadata={"attempts": attempt},
                    )
                    result.record(op)
                    return op
                except Exception as exc:
                    last_error = str(exc)
                    await asyncio.sleep(0.01 * attempt)
            op = OperationResult(
                name=f"retry-{idx}",
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                error=last_error,
                metadata={"attempts": attempt},
            )
            result.record(op)
            return op

        sim = ConcurrentSimulator(workers=self.operations, ramp_up_s=0.5)
        await sim.run(_op)
        recovered = sum(1 for _ in range(self.operations) if injector._attempts.get(f"op-{_}", 0) > 1)
        result.metadata = {
            "max_attempts": self.max_attempts,
            "recovered_keys": recovered,
        }
        result.finish()
        return result


async def _default_operation(idx: int) -> bool:
    await asyncio.sleep(0.005)
    return True
