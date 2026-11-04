"""Durable execution runtime — start, signal, execute steps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from api.constants import DURABLE_EXECUTION_ENABLED
from api.services.durable_execution.compensation import (
    CompensationHandler,
    get_compensation_handler,
)
from api.services.durable_execution.definitions import (
    DefinitionRegistry,
    get_definition_registry,
)
from api.services.durable_execution.events import (
    OrchestrationEventEngine,
    get_orchestration_event_engine,
)
from api.services.durable_execution.persistence import (
    OrchestrationPersistence,
    get_orchestration_persistence,
)
from api.services.durable_execution.platform_bridge import publish_durable_lifecycle_event
from api.services.durable_execution.retry_scheduler import (
    RetryScheduler,
    get_retry_scheduler,
)
from api.services.durable_execution.types import (
    OrchestrationContext,
    OrchestrationEventType,
    OrchestrationResult,
    OrchestrationStatus,
    SagaRecord,
    StepOutcomeType,
)
from api.services.platform_events.schema import PlatformEventType


class DurableExecutionRuntime:
    """Temporal-style durable workflow orchestration runtime."""

    def __init__(
        self,
        persistence: OrchestrationPersistence | None = None,
        events: OrchestrationEventEngine | None = None,
        scheduler: RetryScheduler | None = None,
        compensation: CompensationHandler | None = None,
        definitions: DefinitionRegistry | None = None,
    ) -> None:
        self._persistence = persistence or get_orchestration_persistence()
        self._events = events or get_orchestration_event_engine()
        self._scheduler = scheduler or get_retry_scheduler()
        self._compensation = compensation or get_compensation_handler()
        self._definitions = definitions or get_definition_registry()

    @property
    def enabled(self) -> bool:
        return DURABLE_EXECUTION_ENABLED

    async def start(
        self,
        definition_name: str,
        organization_id: int,
        *,
        orchestration_key: str,
        workflow_run_id: int | None = None,
        initial_state: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> OrchestrationResult:
        definition = self._definitions.get(definition_name)
        existing = await self._persistence.get_by_key(organization_id, orchestration_key)
        if existing is not None:
            return self._persistence.to_result(existing)

        state = dict(initial_state or {})
        state.setdefault("_attempt", 1)
        row = await self._persistence.create_orchestration(
            organization_id=organization_id,
            orchestration_key=orchestration_key,
            definition_name=definition_name,
            workflow_run_id=workflow_run_id,
            entry_step=definition.entry_step,
            initial_state=state,
        )
        await self._events.emit(
            orchestration_id=row.id,
            organization_id=organization_id,
            event_type=OrchestrationEventType.STARTED,
            payload={
                "definition_name": definition_name,
                "orchestration_key": orchestration_key,
                "workflow_run_id": workflow_run_id,
            },
            idempotency_key=idempotency_key or f"start:{organization_id}:{orchestration_key}",
        )
        await publish_durable_lifecycle_event(
            organization_id=organization_id,
            orchestration_id=row.id,
            definition_name=definition_name,
            orchestration_key=orchestration_key,
            event_type=PlatformEventType.ORCHESTRATION_STARTED,
            workflow_run_id=workflow_run_id,
        )
        await self._scheduler.schedule_step_execution(
            orchestration_id=row.id,
            organization_id=organization_id,
            idempotency_key=f"start-exec:{row.id}",
        )
        refreshed = await self._persistence.get_orchestration(row.id)
        return self._persistence.to_result(refreshed or row)

    async def signal(
        self,
        orchestration_id: int,
        signal_type: str,
        payload: dict[str, Any] | None = None,
        *,
        organization_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> OrchestrationResult:
        row = await self._persistence.get_orchestration(
            orchestration_id,
            organization_id=organization_id,
        )
        if row is None:
            raise KeyError(f"Orchestration not found: {orchestration_id}")
        if row.status not in {
            OrchestrationStatus.WAITING.value,
            OrchestrationStatus.SUSPENDED.value,
            OrchestrationStatus.RUNNING.value,
        }:
            return self._persistence.to_result(row)

        emitted = await self._events.emit(
            orchestration_id=orchestration_id,
            organization_id=row.organization_id,
            event_type=OrchestrationEventType.SIGNAL_RECEIVED,
            payload={"signal_type": signal_type, **(payload or {})},
            idempotency_key=idempotency_key,
        )
        if not emitted and idempotency_key:
            return self._persistence.to_result(row)

        await publish_durable_lifecycle_event(
            organization_id=row.organization_id,
            orchestration_id=orchestration_id,
            definition_name=row.definition_name,
            orchestration_key=row.orchestration_key,
            event_type=PlatformEventType.ORCHESTRATION_SIGNAL,
            workflow_run_id=row.workflow_run_id,
            extra={"signal_type": signal_type, **(payload or {})},
        )

        state = dict(row.state or {})
        signals = list(state.get("_signals") or [])
        signals.append({"type": signal_type, "payload": payload or {}})
        state["_signals"] = signals
        state["_last_signal"] = signal_type
        state.update(payload or {})

        updated = await self._persistence.update_orchestration(
            orchestration_id,
            expected_version=row.version,
            status=OrchestrationStatus.RUNNING,
            state=state,
            next_wake_at=None,
        )
        if updated is None:
            raise RuntimeError("Optimistic lock conflict on signal")

        await self._scheduler.schedule_step_execution(
            orchestration_id=orchestration_id,
            organization_id=row.organization_id,
            idempotency_key=f"signal-exec:{orchestration_id}:{idempotency_key or signal_type}",
        )
        refreshed = await self._persistence.get_orchestration(orchestration_id)
        return self._persistence.to_result(refreshed or updated)

    async def execute_current_step(self, orchestration_id: int) -> OrchestrationResult:
        row = await self._persistence.get_orchestration(orchestration_id)
        if row is None:
            raise KeyError(f"Orchestration not found: {orchestration_id}")
        if row.status in {
            OrchestrationStatus.COMPLETED.value,
            OrchestrationStatus.CANCELLED.value,
            OrchestrationStatus.FAILED.value,
            OrchestrationStatus.COMPENSATING.value,
        }:
            return self._persistence.to_result(row)

        definition = self._definitions.get(row.definition_name)
        step_def = definition.step(row.current_step)
        if step_def is None:
            await self._compensation.compensate(
                orchestration_id,
                error=f"unknown step: {row.current_step}",
            )
            refreshed = await self._persistence.get_orchestration(orchestration_id)
            return self._persistence.to_result(refreshed or row)

        saga_stack = self._persistence.parse_saga_stack(row.saga_stack)
        ctx = OrchestrationContext(
            orchestration_id=row.id,
            organization_id=row.organization_id,
            definition_name=row.definition_name,
            orchestration_key=row.orchestration_key,
            workflow_run_id=row.workflow_run_id,
            current_step=row.current_step,
            status=OrchestrationStatus(row.status),
            state=dict(row.state or {}),
            saga_stack=saga_stack,
            attempt=int((row.state or {}).get("_attempt", 1)),
        )

        await self._events.emit(
            orchestration_id=orchestration_id,
            organization_id=row.organization_id,
            event_type=OrchestrationEventType.STEP_STARTED,
            payload={"step_id": row.current_step, "attempt": ctx.attempt},
            idempotency_key=f"step-start:{orchestration_id}:{row.current_step}:v{row.version}",
        )

        running = await self._persistence.update_orchestration(
            orchestration_id,
            expected_version=row.version,
            status=OrchestrationStatus.RUNNING,
        )
        if running is None:
            refreshed = await self._persistence.get_orchestration(orchestration_id)
            return self._persistence.to_result(refreshed or row)

        try:
            outcome = await step_def.handler(ctx)
        except Exception as exc:
            logger.exception(
                "durable step handler failed orch={} step={}",
                orchestration_id,
                row.current_step,
            )
            return await self._handle_step_failure(
                running,
                step_def.max_retries,
                str(exc),
                saga_stack,
            )

        state = dict(running.state or {})
        if outcome.state_updates:
            state.update(outcome.state_updates)

        if outcome.outcome_type == StepOutcomeType.FAIL:
            return await self._handle_step_failure(
                running,
                step_def.max_retries,
                outcome.error or "step failed",
                saga_stack,
                state=state,
            )

        if outcome.outcome_type == StepOutcomeType.WAIT:
            wake_at = outcome.wake_at
            updated = await self._persistence.update_orchestration(
                orchestration_id,
                expected_version=running.version,
                status=OrchestrationStatus.WAITING,
                state=state,
                next_wake_at=wake_at,
            )
            await self._events.emit(
                orchestration_id=orchestration_id,
                organization_id=row.organization_id,
                event_type=OrchestrationEventType.WAITING,
                payload={"step_id": row.current_step, "wake_at": wake_at.isoformat() if wake_at else None},
            )
            if wake_at:
                await self._scheduler.schedule_wake(
                    orchestration_id=orchestration_id,
                    organization_id=row.organization_id,
                    wake_at=wake_at,
                )
            refreshed = await self._persistence.get_orchestration(orchestration_id)
            return self._persistence.to_result(refreshed or updated or running)

        if outcome.outcome_type == StepOutcomeType.SCHEDULE:
            delay = outcome.schedule_delay_s or step_def.retry_delay_s
            wake_at = datetime.now(UTC) + timedelta(seconds=delay)
            updated = await self._persistence.update_orchestration(
                orchestration_id,
                expected_version=running.version,
                status=OrchestrationStatus.WAITING,
                state=state,
                next_wake_at=wake_at,
            )
            await self._scheduler.schedule_wake(
                orchestration_id=orchestration_id,
                organization_id=row.organization_id,
                wake_at=wake_at,
                idempotency_key=f"schedule:{orchestration_id}:{row.current_step}",
            )
            refreshed = await self._persistence.get_orchestration(orchestration_id)
            return self._persistence.to_result(refreshed or updated or running)

        if step_def.compensation_handler is not None:
            saga_stack.append(
                SagaRecord(
                    step_id=row.current_step,
                    compensation_step_id=f"compensate_{row.current_step}",
                    payload=dict(state),
                )
            )

        if outcome.outcome_type == StepOutcomeType.COMPLETE:
            completed = await self._persistence.update_orchestration(
                orchestration_id,
                expected_version=running.version,
                status=OrchestrationStatus.COMPLETED,
                state=state,
                saga_stack=saga_stack,
                completed=True,
            )
            await self._events.emit(
                orchestration_id=orchestration_id,
                organization_id=row.organization_id,
                event_type=OrchestrationEventType.COMPLETED,
                payload={"step_id": row.current_step},
            )
            await publish_durable_lifecycle_event(
                organization_id=row.organization_id,
                orchestration_id=orchestration_id,
                definition_name=row.definition_name,
                orchestration_key=row.orchestration_key,
                event_type=PlatformEventType.ORCHESTRATION_COMPLETED,
                workflow_run_id=row.workflow_run_id,
                extra={"step_id": row.current_step},
            )
            refreshed = await self._persistence.get_orchestration(orchestration_id)
            return self._persistence.to_result(refreshed or completed or running)

        next_step = outcome.next_step
        if outcome.outcome_type == StepOutcomeType.ADVANCE and next_step:
            advanced = await self._persistence.update_orchestration(
                orchestration_id,
                expected_version=running.version,
                status=OrchestrationStatus.RUNNING,
                current_step=next_step,
                state=state,
                saga_stack=saga_stack,
            )
            await self._events.emit(
                orchestration_id=orchestration_id,
                organization_id=row.organization_id,
                event_type=OrchestrationEventType.STEP_COMPLETED,
                payload={"step_id": row.current_step, "next_step": next_step},
            )
            if advanced:
                await self._scheduler.schedule_step_execution(
                    orchestration_id=orchestration_id,
                    organization_id=row.organization_id,
                    idempotency_key=f"advance:{orchestration_id}:{next_step}:v{advanced.version}",
                )
            refreshed = await self._persistence.get_orchestration(orchestration_id)
            return self._persistence.to_result(refreshed or advanced or running)

        refreshed = await self._persistence.get_orchestration(orchestration_id)
        return self._persistence.to_result(refreshed or running)

    async def _handle_step_failure(
        self,
        row: Any,
        max_retries: int,
        error: str,
        saga_stack: list[SagaRecord],
        *,
        state: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        attempt = int((state or row.state or {}).get("_attempt", 1))
        merged_state = dict(state or row.state or {})
        merged_state["_last_error"] = error

        await self._events.emit(
            orchestration_id=row.id,
            organization_id=row.organization_id,
            event_type=OrchestrationEventType.STEP_FAILED,
            payload={"step_id": row.current_step, "error": error, "attempt": attempt},
        )

        if attempt < max_retries:
            merged_state["_attempt"] = attempt + 1
            updated = await self._persistence.update_orchestration(
                row.id,
                expected_version=row.version,
                status=OrchestrationStatus.WAITING,
                state=merged_state,
                saga_stack=saga_stack,
                error_message=error,
            )
            await self._scheduler.schedule_retry(
                orchestration_id=row.id,
                organization_id=row.organization_id,
                attempt=attempt + 1,
                idempotency_key=f"retry:{row.id}:{row.current_step}:{attempt + 1}",
                max_attempts=max_retries,
            )
            refreshed = await self._persistence.get_orchestration(row.id)
            return self._persistence.to_result(refreshed or updated or row)

        await self._compensation.compensate(row.id, error=error)
        refreshed = await self._persistence.get_orchestration(row.id)
        return self._persistence.to_result(refreshed or row)

    async def get_status(
        self,
        orchestration_id: int,
        *,
        organization_id: int | None = None,
    ) -> OrchestrationResult | None:
        row = await self._persistence.get_orchestration(
            orchestration_id,
            organization_id=organization_id,
        )
        if row is None:
            return None
        return self._persistence.to_result(row)


_runtime: DurableExecutionRuntime | None = None


def get_durable_execution_runtime() -> DurableExecutionRuntime:
    global _runtime
    if _runtime is None:
        _runtime = DurableExecutionRuntime()
    return _runtime
