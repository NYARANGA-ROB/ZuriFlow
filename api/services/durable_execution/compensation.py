"""Saga compensation handlers."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.durable_execution.definitions import get_definition_registry
from api.services.durable_execution.events import (
    OrchestrationEventEngine,
    get_orchestration_event_engine,
)
from api.services.durable_execution.persistence import (
    OrchestrationPersistence,
    get_orchestration_persistence,
)
from api.services.durable_execution.types import (
    OrchestrationContext,
    OrchestrationEventType,
    OrchestrationStatus,
    SagaRecord,
    StepOutcome,
    StepOutcomeType,
)
from api.services.durable_execution.platform_bridge import publish_durable_lifecycle_event
from api.services.platform_events.schema import PlatformEventType


class CompensationHandler:
    """Walk saga stack and run compensation steps on failure."""

    def __init__(
        self,
        persistence: OrchestrationPersistence | None = None,
        events: OrchestrationEventEngine | None = None,
    ) -> None:
        self._persistence = persistence or get_orchestration_persistence()
        self._events = events or get_orchestration_event_engine()
        self._definitions = get_definition_registry()

    async def compensate(
        self,
        orchestration_id: int,
        *,
        error: str,
    ) -> dict[str, Any]:
        row = await self._persistence.get_orchestration(orchestration_id)
        if row is None:
            return {"compensated": False, "reason": "not_found"}

        saga_stack = self._persistence.parse_saga_stack(row.saga_stack)
        if not saga_stack:
            await self._mark_failed(row, error)
            return {"compensated": False, "reason": "no_saga_stack", "error": error}

        updated = await self._persistence.update_orchestration(
            orchestration_id,
            expected_version=row.version,
            status=OrchestrationStatus.COMPENSATING,
            error_message=error,
        )
        if updated is None:
            return {"compensated": False, "reason": "version_conflict"}

        await self._events.emit(
            orchestration_id=orchestration_id,
            organization_id=row.organization_id,
            event_type=OrchestrationEventType.COMPENSATION_STARTED,
            payload={"error": error, "steps": len(saga_stack)},
        )

        definition = self._definitions.get(row.definition_name)
        compensated = 0
        errors: list[str] = []

        while saga_stack:
            record = saga_stack.pop()
            if not record.compensation_step_id:
                continue
            comp_step = definition.step(record.compensation_step_id)
            if comp_step is None or comp_step.compensation_handler is None:
                continue
            ctx = self._build_context(updated, saga_stack)
            try:
                outcome = await comp_step.compensation_handler(ctx, record.payload)
                compensated += 1
                if outcome.outcome_type == StepOutcomeType.FAIL:
                    errors.append(outcome.error or "compensation failed")
            except Exception as exc:
                logger.warning(
                    "compensation step failed orch={} step={}: {}",
                    orchestration_id,
                    record.compensation_step_id,
                    exc,
                )
                errors.append(str(exc))

        final_status = (
            OrchestrationStatus.FAILED if errors else OrchestrationStatus.CANCELLED
        )
        await self._persistence.update_orchestration(
            orchestration_id,
            expected_version=updated.version,
            status=final_status,
            saga_stack=saga_stack,
            error_message=error if errors else None,
            completed=True,
        )
        await self._events.emit(
            orchestration_id=orchestration_id,
            organization_id=row.organization_id,
            event_type=OrchestrationEventType.COMPENSATION_COMPLETED,
            payload={"compensated_steps": compensated, "errors": errors},
        )
        if final_status == OrchestrationStatus.FAILED:
            await publish_durable_lifecycle_event(
                organization_id=row.organization_id,
                orchestration_id=orchestration_id,
                definition_name=row.definition_name,
                orchestration_key=row.orchestration_key,
                event_type=PlatformEventType.ORCHESTRATION_FAILED,
                workflow_run_id=row.workflow_run_id,
                extra={"error": error, "errors": errors},
            )
        return {
            "compensated": True,
            "compensated_steps": compensated,
            "errors": errors,
            "status": final_status.value,
        }

    async def run_compensation_step(
        self,
        orchestration_id: int,
        compensation_step_id: str,
        payload: dict[str, Any],
    ) -> StepOutcome:
        row = await self._persistence.get_orchestration(orchestration_id)
        if row is None:
            return StepOutcome.fail("orchestration not found")
        definition = self._definitions.get(row.definition_name)
        comp_step = definition.step(compensation_step_id)
        if comp_step is None or comp_step.compensation_handler is None:
            return StepOutcome.fail(f"no compensation handler for {compensation_step_id}")
        ctx = self._build_context(
            row,
            self._persistence.parse_saga_stack(row.saga_stack),
        )
        return await comp_step.compensation_handler(ctx, payload)

    async def _mark_failed(self, row: Any, error: str) -> None:
        await self._persistence.update_orchestration(
            row.id,
            expected_version=row.version,
            status=OrchestrationStatus.FAILED,
            error_message=error,
            completed=True,
        )
        await self._events.emit(
            orchestration_id=row.id,
            organization_id=row.organization_id,
            event_type=OrchestrationEventType.FAILED,
            payload={"error": error},
        )
        await publish_durable_lifecycle_event(
            organization_id=row.organization_id,
            orchestration_id=row.id,
            definition_name=row.definition_name,
            orchestration_key=row.orchestration_key,
            event_type=PlatformEventType.ORCHESTRATION_FAILED,
            workflow_run_id=row.workflow_run_id,
            extra={"error": error},
        )

    @staticmethod
    def _build_context(
        row: Any,
        saga_stack: list[SagaRecord],
    ) -> OrchestrationContext:
        return OrchestrationContext(
            orchestration_id=row.id,
            organization_id=row.organization_id,
            definition_name=row.definition_name,
            orchestration_key=row.orchestration_key,
            workflow_run_id=row.workflow_run_id,
            current_step=row.current_step,
            status=OrchestrationStatus(row.status),
            state=dict(row.state or {}),
            saga_stack=list(saga_stack),
            attempt=int((row.state or {}).get("_attempt", 1)),
        )


_compensation: CompensationHandler | None = None


def get_compensation_handler() -> CompensationHandler:
    global _compensation
    if _compensation is None:
        _compensation = CompensationHandler()
    return _compensation
