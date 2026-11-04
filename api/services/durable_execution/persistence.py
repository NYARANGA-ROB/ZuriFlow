"""PostgreSQL persistence for durable orchestrations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.db import db_client
from api.db.models import (
    DurableOrchestrationEventModel,
    DurableOrchestrationModel,
    DurableScheduledTaskModel,
)
from api.services.durable_execution.types import (
    OrchestrationEventType,
    OrchestrationResult,
    OrchestrationStatus,
    SagaRecord,
    ScheduledTaskStatus,
    ScheduledTaskType,
)


class OrchestrationPersistence:
    """DB-backed orchestration state with optimistic locking."""

    async def create_orchestration(
        self,
        *,
        organization_id: int,
        orchestration_key: str,
        definition_name: str,
        workflow_run_id: int | None,
        entry_step: str,
        initial_state: dict[str, Any] | None = None,
    ) -> DurableOrchestrationModel:
        return await db_client.create_durable_orchestration(
            organization_id=organization_id,
            orchestration_key=orchestration_key,
            definition_name=definition_name,
            workflow_run_id=workflow_run_id,
            current_step=entry_step,
            state=initial_state or {},
        )

    async def get_orchestration(
        self,
        orchestration_id: int,
        *,
        organization_id: int | None = None,
    ) -> DurableOrchestrationModel | None:
        return await db_client.get_durable_orchestration(
            orchestration_id,
            organization_id=organization_id,
        )

    async def get_by_key(
        self,
        organization_id: int,
        orchestration_key: str,
    ) -> DurableOrchestrationModel | None:
        return await db_client.get_durable_orchestration_by_key(
            organization_id,
            orchestration_key,
        )

    async def list_orchestrations(
        self,
        organization_id: int,
        *,
        status: str | None = None,
        definition_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DurableOrchestrationModel]:
        return await db_client.list_durable_orchestrations(
            organization_id,
            status=status,
            definition_name=definition_name,
            limit=limit,
            offset=offset,
        )

    async def update_orchestration(
        self,
        orchestration_id: int,
        *,
        expected_version: int,
        status: OrchestrationStatus | None = None,
        current_step: str | None = None,
        state: dict[str, Any] | None = None,
        saga_stack: list[SagaRecord] | None = None,
        next_wake_at: datetime | None = None,
        error_message: str | None = None,
        completed: bool = False,
    ) -> DurableOrchestrationModel | None:
        saga_payload = None
        if saga_stack is not None:
            saga_payload = [record.to_dict() for record in saga_stack]
        return await db_client.update_durable_orchestration(
            orchestration_id,
            expected_version=expected_version,
            status=status.value if status else None,
            current_step=current_step,
            state=state,
            saga_stack=saga_payload,
            next_wake_at=next_wake_at,
            error_message=error_message,
            completed=completed,
        )

    async def append_event(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        event_type: OrchestrationEventType,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> DurableOrchestrationEventModel | None:
        return await db_client.append_durable_orchestration_event(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            event_type=event_type.value,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    async def list_events(
        self,
        orchestration_id: int,
        *,
        limit: int = 100,
    ) -> list[DurableOrchestrationEventModel]:
        return await db_client.list_durable_orchestration_events(
            orchestration_id,
            limit=limit,
        )

    async def create_scheduled_task(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        task_type: ScheduledTaskType,
        run_at: datetime,
        payload: dict[str, Any],
        idempotency_key: str,
        max_attempts: int = 5,
    ) -> DurableScheduledTaskModel | None:
        return await db_client.create_durable_scheduled_task(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            task_type=task_type.value,
            run_at=run_at,
            payload=payload,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
        )

    async def claim_due_tasks(
        self,
        *,
        limit: int = 50,
        now: datetime | None = None,
    ) -> list[DurableScheduledTaskModel]:
        return await db_client.claim_due_durable_scheduled_tasks(
            limit=limit,
            now=now or datetime.now(UTC),
        )

    async def complete_scheduled_task(
        self,
        task_id: int,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        await db_client.complete_durable_scheduled_task(
            task_id,
            success=success,
            error=error,
        )

    async def list_stale_orchestrations(
        self,
        *,
        limit: int = 50,
    ) -> list[DurableOrchestrationModel]:
        return await db_client.list_stale_durable_orchestrations(limit=limit)

    @staticmethod
    def to_result(row: DurableOrchestrationModel) -> OrchestrationResult:
        return OrchestrationResult(
            orchestration_id=row.id,
            organization_id=row.organization_id,
            definition_name=row.definition_name,
            orchestration_key=row.orchestration_key,
            status=OrchestrationStatus(row.status),
            current_step=row.current_step,
            state=dict(row.state or {}),
            error_message=row.error_message,
        )

    @staticmethod
    def parse_saga_stack(raw: list[dict[str, Any]] | None) -> list[SagaRecord]:
        return [SagaRecord.from_dict(item) for item in (raw or [])]

    async def increment_task_attempt(self, task_id: int, error: str) -> bool:
        return await db_client.increment_durable_scheduled_task_attempt(
            task_id,
            error=error,
        )


_persistence: OrchestrationPersistence | None = None


def get_orchestration_persistence() -> OrchestrationPersistence:
    global _persistence
    if _persistence is None:
        _persistence = OrchestrationPersistence()
    return _persistence
