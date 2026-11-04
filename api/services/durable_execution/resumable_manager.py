"""Resume orchestrations from persisted checkpoints."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.db.models import DurableOrchestrationModel
from api.services.durable_execution.persistence import (
    OrchestrationPersistence,
    get_orchestration_persistence,
)
from api.services.durable_execution.retry_scheduler import (
    RetryScheduler,
    get_retry_scheduler,
)
from api.services.durable_execution.types import OrchestrationStatus


class ResumableWorkflowManager:
    """Crash recovery and waiting-orchestration wake-up."""

    def __init__(
        self,
        persistence: OrchestrationPersistence | None = None,
        scheduler: RetryScheduler | None = None,
    ) -> None:
        self._persistence = persistence or get_orchestration_persistence()
        self._scheduler = scheduler or get_retry_scheduler()

    async def resume(self, orchestration_id: int) -> dict[str, Any]:
        from api.services.durable_execution.runtime import get_durable_execution_runtime

        row = await self._persistence.get_orchestration(orchestration_id)
        if row is None:
            return {"resumed": False, "reason": "not_found"}
        if row.status in {
            OrchestrationStatus.COMPLETED.value,
            OrchestrationStatus.CANCELLED.value,
        }:
            return {"resumed": False, "reason": "terminal", "status": row.status}

        runtime = get_durable_execution_runtime()
        result = await runtime.execute_current_step(orchestration_id)
        return {"resumed": True, "result": result.to_dict()}

    async def recover_stale(self, *, limit: int = 50) -> dict[str, Any]:
        """Re-enqueue orchestrations stuck in running/waiting past next_wake_at."""
        stale = await self._persistence.list_stale_orchestrations(limit=limit)
        recovered = 0
        for row in stale:
            if await self._recover_row(row):
                recovered += 1
        return {"scanned": len(stale), "recovered": recovered}

    async def _recover_row(self, row: DurableOrchestrationModel) -> bool:
        if row.status == OrchestrationStatus.WAITING.value:
            task_id = await self._scheduler.schedule_step_execution(
                orchestration_id=row.id,
                organization_id=row.organization_id,
                idempotency_key=f"recover:wait:{row.id}:{row.version}",
            )
            if task_id:
                logger.info(
                    "recovered waiting orchestration id={} step={}",
                    row.id,
                    row.current_step,
                )
                return True
            return False

        if row.status == OrchestrationStatus.RUNNING.value:
            task_id = await self._scheduler.schedule_step_execution(
                orchestration_id=row.id,
                organization_id=row.organization_id,
                idempotency_key=f"recover:run:{row.id}:{row.version}",
            )
            if task_id:
                logger.info("recovered running orchestration id={}", row.id)
                return True
        return False


_manager: ResumableWorkflowManager | None = None


def get_resumable_workflow_manager() -> ResumableWorkflowManager:
    global _manager
    if _manager is None:
        _manager = ResumableWorkflowManager()
    return _manager
