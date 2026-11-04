"""Tests for durable workflow orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.durable_execution.definitions import (
    DefinitionRegistry,
    OrchestrationDefinition,
    StepDefinition,
)
from api.services.durable_execution.events import OrchestrationEventEngine
from api.services.durable_execution.persistence import OrchestrationPersistence
from api.services.durable_execution.runtime import DurableExecutionRuntime
from api.services.durable_execution.types import (
    OrchestrationContext,
    OrchestrationStatus,
    StepOutcome,
)


@pytest.fixture(autouse=True)
def _noop_durable_platform_events(monkeypatch):
    async def _noop(**_kwargs):
        return None

    monkeypatch.setattr(
        "api.services.durable_execution.runtime.publish_durable_lifecycle_event",
        _noop,
    )
    monkeypatch.setattr(
        "api.services.durable_execution.compensation.publish_durable_lifecycle_event",
        _noop,
    )


def _mock_orchestration(
    *,
    orch_id: int = 1,
    org_id: int = 10,
    definition_name: str = "test_flow",
    orchestration_key: str = "test:key",
    status: str = OrchestrationStatus.PENDING.value,
    current_step: str = "step_a",
    version: int = 1,
    state: dict | None = None,
):
    row = MagicMock()
    row.id = orch_id
    row.organization_id = org_id
    row.definition_name = definition_name
    row.orchestration_key = orchestration_key
    row.workflow_run_id = None
    row.status = status
    row.current_step = current_step
    row.version = version
    row.state = state or {}
    row.saga_stack = []
    row.error_message = None
    return row


@pytest.mark.asyncio
async def test_start_is_idempotent_by_orchestration_key():
    registry = DefinitionRegistry()

    async def step_a(ctx: OrchestrationContext) -> StepOutcome:
        return StepOutcome.advance("step_b")

    registry.register(
        OrchestrationDefinition(
            name="test_flow",
            entry_step="step_a",
            steps={"step_a": StepDefinition("step_a", step_a)},
        )
    )

    persistence = MagicMock(spec=OrchestrationPersistence)
    existing = _mock_orchestration(status=OrchestrationStatus.RUNNING.value)
    persistence.get_by_key = AsyncMock(return_value=existing)
    persistence.to_result = OrchestrationPersistence.to_result

    runtime = DurableExecutionRuntime(
        persistence=persistence,
        definitions=registry,
        events=MagicMock(spec=OrchestrationEventEngine),
        scheduler=AsyncMock(),
        compensation=AsyncMock(),
    )

    result = await runtime.start(
        "test_flow",
        10,
        orchestration_key="test:key",
    )
    assert result.orchestration_id == 1
    persistence.create_orchestration.assert_not_called()


@pytest.mark.asyncio
async def test_execute_step_advances_on_success():
    registry = DefinitionRegistry()
    calls: list[str] = []

    async def step_a(ctx: OrchestrationContext) -> StepOutcome:
        calls.append("a")
        return StepOutcome.advance("step_b", state_updates={"count": 1})

    async def step_b(ctx: OrchestrationContext) -> StepOutcome:
        calls.append("b")
        return StepOutcome.complete(state_updates={"done": True})

    registry.register(
        OrchestrationDefinition(
            name="test_flow",
            entry_step="step_a",
            steps={
                "step_a": StepDefinition("step_a", step_a),
                "step_b": StepDefinition("step_b", step_b),
            },
        )
    )

    row = _mock_orchestration(current_step="step_a")
    updated_b = _mock_orchestration(
        current_step="step_b",
        status=OrchestrationStatus.RUNNING.value,
        version=2,
        state={"count": 1},
    )
    completed = _mock_orchestration(
        current_step="step_b",
        status=OrchestrationStatus.COMPLETED.value,
        version=3,
        state={"count": 1, "done": True},
    )

    persistence = MagicMock(spec=OrchestrationPersistence)
    persistence.get_orchestration = AsyncMock(
        side_effect=[row, updated_b, completed, completed]
    )
    persistence.parse_saga_stack = OrchestrationPersistence.parse_saga_stack
    persistence.update_orchestration = AsyncMock(
        side_effect=[updated_b, completed]
    )
    persistence.to_result = OrchestrationPersistence.to_result

    events = MagicMock(spec=OrchestrationEventEngine)
    events.emit = AsyncMock(return_value=True)
    scheduler = AsyncMock()
    scheduler.schedule_step_execution = AsyncMock(return_value=99)

    runtime = DurableExecutionRuntime(
        persistence=persistence,
        definitions=registry,
        events=events,
        scheduler=scheduler,
        compensation=AsyncMock(),
    )

    result = await runtime.execute_current_step(1)
    assert result.status == OrchestrationStatus.RUNNING
    assert result.current_step == "step_b"
    assert result.state.get("count") == 1
    assert calls == ["a"]
    scheduler.schedule_step_execution.assert_awaited_once()


@pytest.mark.asyncio
async def test_signal_resumes_waiting_orchestration():
    registry = DefinitionRegistry()

    async def wait_step(ctx: OrchestrationContext) -> StepOutcome:
        if ctx.state.get("_last_signal") == "payment.completed":
            return StepOutcome.complete()
        return StepOutcome.wait(
            wake_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    registry.register(
        OrchestrationDefinition(
            name="payment_wait",
            entry_step="wait",
            steps={"wait": StepDefinition("wait", wait_step)},
        )
    )

    waiting = _mock_orchestration(
        status=OrchestrationStatus.WAITING.value,
        current_step="wait",
    )
    running = _mock_orchestration(
        status=OrchestrationStatus.RUNNING.value,
        current_step="wait",
        version=2,
        state={"_last_signal": "payment.completed", "payment_status": "completed"},
    )

    persistence = MagicMock(spec=OrchestrationPersistence)
    persistence.get_orchestration = AsyncMock(
        side_effect=[waiting, running, running]
    )
    persistence.update_orchestration = AsyncMock(return_value=running)
    persistence.to_result = OrchestrationPersistence.to_result

    events = MagicMock(spec=OrchestrationEventEngine)
    events.emit = AsyncMock(return_value=True)
    scheduler = AsyncMock()
    scheduler.schedule_step_execution = AsyncMock(return_value=1)

    runtime = DurableExecutionRuntime(
        persistence=persistence,
        definitions=registry,
        events=events,
        scheduler=scheduler,
        compensation=AsyncMock(),
    )

    result = await runtime.signal(
        1,
        "payment.completed",
        {"payment_status": "completed"},
        organization_id=10,
        idempotency_key="sig-1",
    )
    assert result.status == OrchestrationStatus.RUNNING
    scheduler.schedule_step_execution.assert_awaited_once()


@pytest.mark.asyncio
async def test_step_failure_schedules_retry_before_compensation():
    registry = DefinitionRegistry()

    async def flaky(ctx: OrchestrationContext) -> StepOutcome:
        return StepOutcome.fail("transient error")

    registry.register(
        OrchestrationDefinition(
            name="flaky",
            entry_step="work",
            steps={
                "work": StepDefinition("work", flaky, max_retries=3, retry_delay_s=10),
            },
        )
    )

    row = _mock_orchestration(
        definition_name="flaky",
        current_step="work",
        state={"_attempt": 1},
    )
    waiting = _mock_orchestration(
        definition_name="flaky",
        status=OrchestrationStatus.WAITING.value,
        current_step="work",
        version=2,
        state={"_attempt": 2, "_last_error": "transient error"},
    )

    persistence = MagicMock(spec=OrchestrationPersistence)
    persistence.get_orchestration = AsyncMock(side_effect=[row, waiting])
    persistence.parse_saga_stack = OrchestrationPersistence.parse_saga_stack
    persistence.update_orchestration = AsyncMock(return_value=waiting)
    persistence.to_result = OrchestrationPersistence.to_result

    events = MagicMock(spec=OrchestrationEventEngine)
    events.emit = AsyncMock(return_value=True)
    scheduler = AsyncMock()
    scheduler.schedule_retry = AsyncMock(return_value=42)
    compensation = AsyncMock()
    compensation.compensate = AsyncMock()

    runtime = DurableExecutionRuntime(
        persistence=persistence,
        definitions=registry,
        events=events,
        scheduler=scheduler,
        compensation=compensation,
    )

    result = await runtime.execute_current_step(1)
    assert result.status == OrchestrationStatus.WAITING
    scheduler.schedule_retry.assert_awaited_once()
    compensation.compensate.assert_not_called()


def test_builtin_definitions_registered():
    from api.services.durable_execution.definitions import get_definition_registry

    registry = get_definition_registry()
    names = registry.list_names()
    assert "post_call_whatsapp" in names
    assert "mpesa_payment_wait" in names
