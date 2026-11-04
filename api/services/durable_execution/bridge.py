"""Integration bridge — start durable orchestrations from existing flows."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.constants import DURABLE_EXECUTION_ENABLED
from api.services.durable_execution.runtime import get_durable_execution_runtime
from api.services.durable_execution.types import OrchestrationResult


class DurableExecutionBridge:
    """Entry points for wiring durable orchestration into platform flows."""

    async def start_post_call_whatsapp(
        self,
        *,
        workflow_run_id: int,
        organization_id: int,
        resume_from_step: str | None = None,
        attempt: int = 1,
    ) -> OrchestrationResult | None:
        if not DURABLE_EXECUTION_ENABLED:
            return None
        runtime = get_durable_execution_runtime()
        key = f"post_call_whatsapp:run:{workflow_run_id}"
        return await runtime.start(
            "post_call_whatsapp",
            organization_id,
            orchestration_key=key,
            workflow_run_id=workflow_run_id,
            initial_state={
                "workflow_run_id": workflow_run_id,
                "resume_from_step": resume_from_step,
                "_attempt": attempt,
            },
            idempotency_key=f"start:post_call:{workflow_run_id}",
        )

    async def start_mpesa_payment_wait(
        self,
        *,
        organization_id: int,
        transaction_id: int,
        workflow_run_id: int | None = None,
        callback_timeout_s: float = 300,
        max_payment_retries: int = 3,
    ) -> OrchestrationResult | None:
        if not DURABLE_EXECUTION_ENABLED:
            return None
        runtime = get_durable_execution_runtime()
        key = f"mpesa_payment_wait:txn:{transaction_id}"
        return await runtime.start(
            "mpesa_payment_wait",
            organization_id,
            orchestration_key=key,
            workflow_run_id=workflow_run_id,
            initial_state={
                "transaction_id": transaction_id,
                "callback_timeout_s": callback_timeout_s,
                "max_payment_retries": max_payment_retries,
                "payment_attempt": 1,
            },
            idempotency_key=f"start:mpesa:{transaction_id}",
        )

    async def signal_payment_completed(
        self,
        orchestration_id: int,
        *,
        organization_id: int,
        payload: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        runtime = get_durable_execution_runtime()
        return await runtime.signal(
            orchestration_id,
            "payment.completed",
            {"payment_status": "completed", **(payload or {})},
            organization_id=organization_id,
            idempotency_key=f"payment.completed:{orchestration_id}",
        )

    async def signal_payment_failed(
        self,
        orchestration_id: int,
        *,
        organization_id: int,
        payload: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        runtime = get_durable_execution_runtime()
        return await runtime.signal(
            orchestration_id,
            "payment.failed",
            {"payment_status": "failed", **(payload or {})},
            organization_id=organization_id,
            idempotency_key=f"payment.failed:{orchestration_id}",
        )


_bridge: DurableExecutionBridge | None = None


def get_durable_execution_bridge() -> DurableExecutionBridge:
    global _bridge
    if _bridge is None:
        _bridge = DurableExecutionBridge()
    return _bridge


async def maybe_start_post_call_durable(
    workflow_run_id: int,
    organization_id: int,
) -> bool:
    """Start post-call via durable engine if enabled. Returns True if delegated."""
    bridge = get_durable_execution_bridge()
    result = await bridge.start_post_call_whatsapp(
        workflow_run_id=workflow_run_id,
        organization_id=organization_id,
    )
    if result is None:
        return False
    logger.info(
        "delegated post-call WhatsApp to durable orchestration id={} run_id={}",
        result.orchestration_id,
        workflow_run_id,
    )
    return True
