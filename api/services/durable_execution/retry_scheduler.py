"""ARQ-backed retry and delayed task scheduling."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from api.constants import DURABLE_EXECUTION_RETRY_BASE_DELAY_S
from api.services.durable_execution.persistence import (
    OrchestrationPersistence,
    get_orchestration_persistence,
)
from api.services.durable_execution.types import ScheduledTaskType
from api.tasks.function_names import FunctionNames


class RetryScheduler:
    """Schedule durable orchestration work via DB + ARQ."""

    def __init__(
        self,
        persistence: OrchestrationPersistence | None = None,
        *,
        base_delay_s: float = DURABLE_EXECUTION_RETRY_BASE_DELAY_S,
    ) -> None:
        self._persistence = persistence or get_orchestration_persistence()
        self._base_delay_s = base_delay_s

    def delay_for_attempt(self, attempt: int) -> float:
        return self._base_delay_s * (2 ** max(0, attempt - 1))

    async def schedule_step_execution(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        delay_s: float = 0,
        idempotency_key: str | None = None,
        max_attempts: int = 5,
    ) -> int | None:
        run_at = datetime.now(UTC) + timedelta(seconds=max(0.0, delay_s))
        key = idempotency_key or f"exec:{orchestration_id}:{uuid.uuid4().hex}"
        task = await self._persistence.create_scheduled_task(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            task_type=ScheduledTaskType.EXECUTE_STEP,
            run_at=run_at,
            payload={"orchestration_id": orchestration_id},
            idempotency_key=key,
            max_attempts=max_attempts,
        )
        if task is None:
            return None
        if delay_s <= 0:
            await self._enqueue_arq(task.id, orchestration_id)
        return task.id

    async def schedule_retry(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        attempt: int,
        idempotency_key: str | None = None,
        max_attempts: int = 5,
    ) -> int | None:
        delay = self.delay_for_attempt(attempt)
        key = idempotency_key or f"retry:{orchestration_id}:{attempt}:{int(time.time())}"
        task = await self._persistence.create_scheduled_task(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            task_type=ScheduledTaskType.RETRY_STEP,
            run_at=datetime.now(UTC) + timedelta(seconds=delay),
            payload={"orchestration_id": orchestration_id, "attempt": attempt},
            idempotency_key=key,
            max_attempts=max_attempts,
        )
        if task is None:
            return None
        return task.id

    async def schedule_wake(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        wake_at: datetime,
        idempotency_key: str | None = None,
    ) -> int | None:
        key = idempotency_key or f"wake:{orchestration_id}:{int(wake_at.timestamp())}"
        task = await self._persistence.create_scheduled_task(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            task_type=ScheduledTaskType.WAKE_ORCHESTRATION,
            run_at=wake_at,
            payload={"orchestration_id": orchestration_id},
            idempotency_key=key,
        )
        return task.id if task else None

    async def schedule_compensation(
        self,
        *,
        orchestration_id: int,
        organization_id: int,
        compensation_step_id: str,
        payload: dict[str, Any] | None = None,
    ) -> int | None:
        key = f"compensate:{orchestration_id}:{compensation_step_id}:{uuid.uuid4().hex[:8]}"
        task = await self._persistence.create_scheduled_task(
            orchestration_id=orchestration_id,
            organization_id=organization_id,
            task_type=ScheduledTaskType.COMPENSATE,
            run_at=datetime.now(UTC),
            payload={
                "orchestration_id": orchestration_id,
                "compensation_step_id": compensation_step_id,
                **(payload or {}),
            },
            idempotency_key=key,
        )
        if task is None:
            return None
        await self._enqueue_arq(task.id, orchestration_id)
        return task.id

    async def process_due_tasks(self, *, limit: int = 50) -> dict[str, Any]:
        tasks = await self._persistence.claim_due_tasks(limit=limit)
        processed = 0
        failed = 0
        for task in tasks:
            try:
                await self._enqueue_arq(task.id, task.orchestration_id)
                processed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "failed to enqueue durable task id={}: {}",
                    task.id,
                    exc,
                )
                await self._persistence.complete_scheduled_task(
                    task.id,
                    success=False,
                    error=str(exc),
                )
        return {"claimed": len(tasks), "enqueued": processed, "failed": failed}

    async def _enqueue_arq(self, task_id: int, orchestration_id: int) -> None:
        from api.tasks.arq import get_arq_redis

        redis = await get_arq_redis()
        await redis.enqueue_job(
            FunctionNames.PROCESS_DURABLE_ORCHESTRATION_TASK,
            task_id,
            orchestration_id,
        )


_scheduler: RetryScheduler | None = None


def get_retry_scheduler() -> RetryScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = RetryScheduler()
    return _scheduler
