from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from api.services.reliability_testing.concurrent_simulator import ConcurrentSimulator
from api.services.reliability_testing.types import OperationResult, ScenarioResult, StressScenario


@dataclass
class STKPushSpikeSimulator:
    """Simulate concurrent M-Pesa STK push requests."""

    organization_id: int = 1
    spike_size: int = 50
    fail_rate: float = 0.1
    latency_ms: float = 120.0
    jitter_ms: float = 40.0

    async def run(self, *, stk_fn: Callable[..., Awaitable[Any]] | None = None) -> ScenarioResult:
        result = ScenarioResult(scenario=StressScenario.STK_PUSH_SPIKE)
        result.metadata = {
            "spike_size": self.spike_size,
            "fail_rate": self.fail_rate,
        }

        async def _push(idx: int) -> OperationResult:
            start = time.perf_counter()
            phone = f"+2547{idx:08d}"[-13:]
            try:
                if stk_fn is None:
                    await asyncio.sleep(
                        max(
                            0.001,
                            (self.latency_ms + random.uniform(-self.jitter_ms, self.jitter_ms))
                            / 1000.0,
                        )
                    )
                    if random.random() < self.fail_rate:
                        raise RuntimeError("simulated daraja timeout")
                else:
                    response = await stk_fn(phone_e164=phone, amount=100.0, organization_id=self.organization_id)
                    if not getattr(response, "success", True):
                        raise RuntimeError("stk push failed")
                op = OperationResult(
                    name=f"stk-{idx}",
                    success=True,
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    metadata={"phone": phone},
                )
                result.record(op)
                return op
            except Exception as exc:
                op = OperationResult(
                    name=f"stk-{idx}",
                    success=False,
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    error=str(exc),
                )
                result.record(op)
                return op

        sim = ConcurrentSimulator(workers=self.spike_size, ramp_up_s=0.5)
        await sim.run(_push)
        result.finish()
        return result


@dataclass
class WhatsAppSpikeSimulator:
    """Simulate burst WhatsApp outbound enqueue + retry pressure."""

    organization_id: int = 1
    spike_size: int = 100
    fail_rate: float = 0.15
    retry_on_failure: bool = True

    async def run(
        self,
        *,
        send_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    ) -> ScenarioResult:
        result = ScenarioResult(scenario=StressScenario.WHATSAPP_SPIKE)
        result.metadata = {
            "spike_size": self.spike_size,
            "fail_rate": self.fail_rate,
            "retry_on_failure": self.retry_on_failure,
        }
        retries = 0

        async def _send(idx: int) -> OperationResult:
            nonlocal retries
            start = time.perf_counter()
            attempt = 0
            last_error = ""
            while attempt < 3:
                attempt += 1
                try:
                    if send_fn is None:
                        await asyncio.sleep(0.01)
                        success = random.random() >= self.fail_rate
                        if not success:
                            raise RuntimeError("simulated whatsapp provider 503")
                        op = OperationResult(
                            name=f"wa-{idx}",
                            success=True,
                            latency_ms=(time.perf_counter() - start) * 1000.0,
                            metadata={"attempts": attempt},
                        )
                        result.record(op)
                        return op
                    payload = {
                        "organization_id": self.organization_id,
                        "phone_e164": f"+2547{idx:08d}"[-13:],
                        "body": f"load test {idx}",
                        "attempt": attempt,
                    }
                    response = await send_fn(payload)
                    if response.get("success"):
                        op = OperationResult(
                            name=f"wa-{idx}",
                            success=True,
                            latency_ms=(time.perf_counter() - start) * 1000.0,
                            metadata={"attempts": attempt},
                        )
                        result.record(op)
                        return op
                    last_error = str(response.get("error", "send failed"))
                except Exception as exc:
                    last_error = str(exc)
                if self.retry_on_failure:
                    retries += 1
                    await asyncio.sleep(0.005 * attempt)
                else:
                    break
            op = OperationResult(
                name=f"wa-{idx}",
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                error=last_error,
                metadata={"attempts": attempt},
            )
            result.record(op)
            return op

        sim = ConcurrentSimulator(workers=self.spike_size, ramp_up_s=1.0)
        await sim.run(_send)
        result.metadata["retries"] = retries
        result.finish()
        return result
