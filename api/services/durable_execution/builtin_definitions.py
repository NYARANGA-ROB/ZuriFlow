"""Built-in orchestration definitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from api.services.durable_execution.definitions import (
    DefinitionRegistry,
    OrchestrationDefinition,
    StepDefinition,
)
from api.services.durable_execution.types import OrchestrationContext, StepOutcome


async def _noop_compensate(ctx: OrchestrationContext, payload: dict) -> StepOutcome:
    logger.info(
        "compensating step={} orch={} payload_keys={}",
        ctx.current_step,
        ctx.orchestration_id,
        list(payload.keys()),
    )
    return StepOutcome.complete(state_updates={"compensated": True})


# --- post_call_whatsapp ---

async def _post_call_execute(ctx: OrchestrationContext) -> StepOutcome:
    from api.services.whatsapp.post_call.orchestrator import PostCallWhatsAppOrchestrator

    workflow_run_id = ctx.workflow_run_id or int(ctx.state.get("workflow_run_id", 0))
    if not workflow_run_id:
        return StepOutcome.fail("workflow_run_id missing")

    resume_from = ctx.state.get("resume_from_step")
    attempt = int(ctx.state.get("_attempt", ctx.attempt))
    orchestrator = PostCallWhatsAppOrchestrator()
    result = await orchestrator.run(
        workflow_run_id,
        resume_from_step=resume_from,
        attempt=attempt,
    )

    if result.skipped:
        return StepOutcome.complete(
            state_updates={"skipped": True, "skip_reason": result.skip_reason},
        )
    if result.success:
        return StepOutcome.complete(state_updates={"post_call": result.to_dict()})

    failed_step = next((s for s in result.steps if not s.success), None)
    if failed_step:
        return StepOutcome.schedule(
            delay_s=30.0,
            state_updates={
                "resume_from_step": failed_step.step.value,
                "post_call_partial": result.to_dict(),
            },
        )
    return StepOutcome.fail("post-call workflow incomplete")


# --- mpesa_payment_wait ---

async def _mpesa_record_pending(ctx: OrchestrationContext) -> StepOutcome:
    transaction_id = ctx.state.get("transaction_id")
    if not transaction_id:
        return StepOutcome.fail("transaction_id required")
    return StepOutcome.advance(
        "wait_callback",
        state_updates={"recorded_at": datetime.now(UTC).isoformat()},
    )


async def _mpesa_wait_callback(ctx: OrchestrationContext) -> StepOutcome:
    last_signal = ctx.state.get("_last_signal")
    status = (ctx.state.get("payment_status") or "").lower()

    if last_signal == "payment.completed" or status in {"completed", "success"}:
        return StepOutcome.advance("finalize_success")
    if last_signal == "payment.failed" or status in {"failed", "cancelled"}:
        return StepOutcome.advance("handle_failure")

    timeout_s = float(ctx.state.get("callback_timeout_s", 300))
    started = ctx.state.get("recorded_at")
    if started:
        started_dt = datetime.fromisoformat(str(started))
        if datetime.now(UTC) - started_dt > timedelta(seconds=timeout_s):
            return StepOutcome.advance(
                "handle_failure",
                state_updates={"timed_out": True},
            )

    if ctx.state.get("waiting_for") == "payment_callback":
        return StepOutcome.advance("verify_pending")

    verify_after_s = float(ctx.state.get("verify_after_s", 60))
    return StepOutcome.wait(
        wake_at=datetime.now(UTC) + timedelta(seconds=verify_after_s),
        state_updates={"waiting_for": "payment_callback"},
    )


async def _mpesa_verify_pending(ctx: OrchestrationContext) -> StepOutcome:
    transaction_id = int(ctx.state.get("transaction_id", 0))
    if not transaction_id:
        return StepOutcome.fail("transaction_id missing")

    from api.db import db_client

    txn = await db_client.get_transaction(
        transaction_id,
        organization_id=ctx.organization_id,
    )
    if txn is None:
        return StepOutcome.fail("transaction not found")

    status = str(txn.status).lower()
    if status in {"completed", "success"}:
        return StepOutcome.advance(
            "finalize_success",
            state_updates={"payment_status": status, "verified": True},
        )
    if status in {"failed", "cancelled"}:
        return StepOutcome.advance(
            "handle_failure",
            state_updates={"payment_status": status},
        )
    return StepOutcome.wait(
        wake_at=datetime.now(UTC) + timedelta(seconds=60),
    )


async def _mpesa_finalize_success(ctx: OrchestrationContext) -> StepOutcome:
    return StepOutcome.complete(
        state_updates={"outcome": "payment_succeeded"},
    )


async def _mpesa_handle_failure(ctx: OrchestrationContext) -> StepOutcome:
    max_retries = int(ctx.state.get("max_payment_retries", 3))
    payment_attempt = int(ctx.state.get("payment_attempt", 1))
    if payment_attempt < max_retries and not ctx.state.get("timed_out"):
        return StepOutcome.advance(
            "record_pending",
            state_updates={"payment_attempt": payment_attempt + 1, "_attempt": 1},
        )
    return StepOutcome.fail("payment failed after retries")


async def _mpesa_compensate_record(ctx: OrchestrationContext, payload: dict) -> StepOutcome:
    logger.info(
        "M-Pesa compensation orch={} txn={}",
        ctx.orchestration_id,
        payload.get("transaction_id") or ctx.state.get("transaction_id"),
    )
    return StepOutcome.complete()


def register_builtin_definitions(registry: DefinitionRegistry) -> None:
    registry.register(
        OrchestrationDefinition(
            name="post_call_whatsapp",
            entry_step="execute",
            steps={
                "execute": StepDefinition(
                    step_id="execute",
                    handler=_post_call_execute,
                    max_retries=5,
                    retry_delay_s=30.0,
                ),
            },
            terminal_steps=frozenset({"execute"}),
        )
    )

    registry.register(
        OrchestrationDefinition(
            name="mpesa_payment_wait",
            entry_step="record_pending",
            steps={
                "record_pending": StepDefinition(
                    step_id="record_pending",
                    handler=_mpesa_record_pending,
                    compensation_handler=_mpesa_compensate_record,
                    max_retries=3,
                ),
                "wait_callback": StepDefinition(
                    step_id="wait_callback",
                    handler=_mpesa_wait_callback,
                    max_retries=10,
                    retry_delay_s=60.0,
                ),
                "verify_pending": StepDefinition(
                    step_id="verify_pending",
                    handler=_mpesa_verify_pending,
                    max_retries=5,
                    retry_delay_s=60.0,
                ),
                "finalize_success": StepDefinition(
                    step_id="finalize_success",
                    handler=_mpesa_finalize_success,
                ),
                "handle_failure": StepDefinition(
                    step_id="handle_failure",
                    handler=_mpesa_handle_failure,
                    compensation_handler=_mpesa_compensate_record,
                ),
                "compensate_record_pending": StepDefinition(
                    step_id="compensate_record_pending",
                    handler=_mpesa_compensate_record,
                    compensation_handler=_mpesa_compensate_record,
                ),
            },
        )
    )
