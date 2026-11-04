"""Database operations for durable orchestrations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from api.db.base_client import BaseDBClient
from api.db.models import (
    DurableOrchestrationEventModel,
    DurableOrchestrationModel,
    DurableScheduledTaskModel,
)
from api.services.durable_execution.types import OrchestrationStatus, ScheduledTaskStatus


class DurableOrchestrationClient(BaseDBClient):
    async def create_durable_orchestration(
        self,
        *,
        organization_id: int,
        orchestration_key: str,
        definition_name: str,
        workflow_run_id: int | None,
        current_step: str,
        state: dict[str, Any],
    ) -> DurableOrchestrationModel:
        async with self.async_session() as session:
            row = DurableOrchestrationModel(
                organization_id=organization_id,
                orchestration_key=orchestration_key,
                definition_name=definition_name,
                workflow_run_id=workflow_run_id,
                status=OrchestrationStatus.PENDING.value,
                current_step=current_step,
                state=state,
                saga_stack=[],
                version=1,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_durable_orchestration(
        self,
        orchestration_id: int,
        *,
        organization_id: int | None = None,
    ) -> DurableOrchestrationModel | None:
        async with self.async_session() as session:
            query = select(DurableOrchestrationModel).where(
                DurableOrchestrationModel.id == orchestration_id
            )
            if organization_id is not None:
                query = query.where(
                    DurableOrchestrationModel.organization_id == organization_id
                )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_durable_orchestration_by_key(
        self,
        organization_id: int,
        orchestration_key: str,
    ) -> DurableOrchestrationModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(DurableOrchestrationModel).where(
                    DurableOrchestrationModel.organization_id == organization_id,
                    DurableOrchestrationModel.orchestration_key == orchestration_key,
                )
            )
            return result.scalar_one_or_none()

    async def list_durable_orchestrations(
        self,
        organization_id: int,
        *,
        status: str | None = None,
        definition_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DurableOrchestrationModel]:
        async with self.async_session() as session:
            query = select(DurableOrchestrationModel).where(
                DurableOrchestrationModel.organization_id == organization_id
            )
            if status:
                query = query.where(DurableOrchestrationModel.status == status)
            if definition_name:
                query = query.where(
                    DurableOrchestrationModel.definition_name == definition_name
                )
            query = (
                query.order_by(DurableOrchestrationModel.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_durable_orchestration(
        self,
        orchestration_id: int,
        *,
        expected_version: int,
        status: str | None = None,
        current_step: str | None = None,
        state: dict[str, Any] | None = None,
        saga_stack: list[dict[str, Any]] | None = None,
        next_wake_at: datetime | None = None,
        error_message: str | None = None,
        completed: bool = False,
        clear_wake: bool = False,
    ) -> DurableOrchestrationModel | None:
        async with self.async_session() as session:
            values: dict[str, Any] = {
                "version": expected_version + 1,
                "updated_at": datetime.now(UTC),
            }
            if status is not None:
                values["status"] = status
            if current_step is not None:
                values["current_step"] = current_step
            if state is not None:
                values["state"] = state
            if saga_stack is not None:
                values["saga_stack"] = saga_stack
            if clear_wake:
                values["next_wake_at"] = None
            elif next_wake_at is not None:
                values["next_wake_at"] = next_wake_at
            if error_message is not None:
                values["error_message"] = error_message
            if completed:
                values["completed_at"] = datetime.now(UTC)

            stmt = (
                update(DurableOrchestrationModel)
                .where(
                    DurableOrchestrationModel.id == orchestration_id,
                    DurableOrchestrationModel.version == expected_version,
                )
                .values(**values)
                .returning(DurableOrchestrationModel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                await session.rollback()
                return None
            await session.commit()
            return row

    async def append_durable_orchestration_event(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> DurableOrchestrationEventModel | None:
        async with self.async_session() as session:
            if idempotency_key:
                existing = await session.execute(
                    select(DurableOrchestrationEventModel).where(
                        DurableOrchestrationEventModel.idempotency_key == idempotency_key
                    )
                )
                found = existing.scalar_one_or_none()
                if found:
                    return found

            row = DurableOrchestrationEventModel(
                orchestration_id=orchestration_id,
                organization_id=organization_id,
                event_type=event_type,
                payload=payload,
                idempotency_key=idempotency_key,
            )
            session.add(row)
            try:
                await session.commit()
                await session.refresh(row)
                return row
            except Exception:
                await session.rollback()
                if idempotency_key:
                    result = await session.execute(
                        select(DurableOrchestrationEventModel).where(
                            DurableOrchestrationEventModel.idempotency_key
                            == idempotency_key
                        )
                    )
                    return result.scalar_one_or_none()
                raise

    async def list_durable_orchestration_events(
        self,
        orchestration_id: int,
        *,
        limit: int = 100,
    ) -> list[DurableOrchestrationEventModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(DurableOrchestrationEventModel)
                .where(DurableOrchestrationEventModel.orchestration_id == orchestration_id)
                .order_by(DurableOrchestrationEventModel.id.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def create_durable_scheduled_task(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        task_type: str,
        run_at: datetime,
        payload: dict[str, Any],
        idempotency_key: str,
        max_attempts: int = 5,
    ) -> DurableScheduledTaskModel | None:
        async with self.async_session() as session:
            stmt = (
                insert(DurableScheduledTaskModel)
                .values(
                    orchestration_id=orchestration_id,
                    organization_id=organization_id,
                    task_type=task_type,
                    run_at=run_at,
                    payload=payload,
                    status=ScheduledTaskStatus.PENDING.value,
                    attempt=0,
                    max_attempts=max_attempts,
                    idempotency_key=idempotency_key,
                )
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(DurableScheduledTaskModel)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            await session.commit()
            if row is None:
                existing = await session.execute(
                    select(DurableScheduledTaskModel).where(
                        DurableScheduledTaskModel.idempotency_key == idempotency_key
                    )
                )
                return existing.scalar_one_or_none()
            return row

    async def claim_due_durable_scheduled_tasks(
        self,
        *,
        limit: int = 50,
        now: datetime | None = None,
    ) -> list[DurableScheduledTaskModel]:
        due = now or datetime.now(UTC)
        async with self.async_session() as session:
            result = await session.execute(
                select(DurableScheduledTaskModel)
                .where(
                    DurableScheduledTaskModel.status == ScheduledTaskStatus.PENDING.value,
                    DurableScheduledTaskModel.run_at <= due,
                )
                .order_by(DurableScheduledTaskModel.run_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = list(result.scalars().all())
            for row in rows:
                row.status = ScheduledTaskStatus.CLAIMED.value
                row.updated_at = datetime.now(UTC)
            await session.commit()
            return rows

    async def complete_durable_scheduled_task(
        self,
        task_id: int,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        async with self.async_session() as session:
            status = (
                ScheduledTaskStatus.COMPLETED.value
                if success
                else ScheduledTaskStatus.FAILED.value
            )
            await session.execute(
                update(DurableScheduledTaskModel)
                .where(DurableScheduledTaskModel.id == task_id)
                .values(
                    status=status,
                    last_error=error,
                    completed_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

    async def increment_durable_scheduled_task_attempt(
        self,
        task_id: int,
        *,
        error: str,
    ) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(DurableScheduledTaskModel).where(
                    DurableScheduledTaskModel.id == task_id
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return False
            row.attempt += 1
            row.last_error = error
            row.updated_at = datetime.now(UTC)
            if row.attempt >= row.max_attempts:
                row.status = ScheduledTaskStatus.FAILED.value
                row.completed_at = datetime.now(UTC)
            else:
                row.status = ScheduledTaskStatus.PENDING.value
                row.run_at = datetime.now(UTC)
            await session.commit()
            return row.status == ScheduledTaskStatus.PENDING.value

    async def list_stale_durable_orchestrations(
        self,
        *,
        limit: int = 50,
    ) -> list[DurableOrchestrationModel]:
        now = datetime.now(UTC)
        async with self.async_session() as session:
            result = await session.execute(
                select(DurableOrchestrationModel)
                .where(
                    or_(
                        and_(
                            DurableOrchestrationModel.status
                            == OrchestrationStatus.WAITING.value,
                            DurableOrchestrationModel.next_wake_at <= now,
                        ),
                        DurableOrchestrationModel.status
                        == OrchestrationStatus.RUNNING.value,
                    )
                )
                .order_by(DurableOrchestrationModel.updated_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_durable_scheduled_task(
        self,
        task_id: int,
    ) -> DurableScheduledTaskModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(DurableScheduledTaskModel).where(
                    DurableScheduledTaskModel.id == task_id
                )
            )
            return result.scalar_one_or_none()
