"""ARQ tasks for durable orchestration."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.durable_execution.compensation import get_compensation_handler
from api.services.durable_execution.resumable_manager import get_resumable_workflow_manager
from api.services.durable_execution.retry_scheduler import get_retry_scheduler
from api.services.durable_execution.runtime import get_durable_execution_runtime
from api.services.durable_execution.types import ScheduledTaskType


async def process_durable_orchestration_task(
    _ctx: dict[str, Any],
    task_id: int,
    orchestration_id: int,
) -> dict[str, Any]:
    """Execute a claimed durable scheduled task."""
    runtime = get_durable_execution_runtime()
    compensation = get_compensation_handler()

    task = await db_client.get_durable_scheduled_task(task_id)
    if task is None:
        return {"ok": False, "reason": "task_not_found"}

    task_type = task.task_type
    try:
        if task_type == ScheduledTaskType.COMPENSATE.value:
            step_id = (task.payload or {}).get("compensation_step_id", "")
            outcome = await compensation.run_compensation_step(
                orchestration_id,
                step_id,
                dict(task.payload or {}),
            )
            ok = outcome.outcome_type.value != "fail"
        else:
            result = await runtime.execute_current_step(orchestration_id)
            ok = result.status.value not in {"failed", "compensating"}
        await db_client.complete_durable_scheduled_task(task_id, success=ok)
        return {"ok": ok, "orchestration_id": orchestration_id, "task_type": task_type}
    except Exception as exc:
        logger.exception(
            "durable orchestration task failed task_id={} orch={}",
            task_id,
            orchestration_id,
        )
        retry = await db_client.increment_durable_scheduled_task_attempt(
            task_id, error=str(exc)
        )
        if not retry:
            await db_client.complete_durable_scheduled_task(
                task_id, success=False, error=str(exc)
            )
        raise


async def process_all_durable_scheduled_tasks(_ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron: enqueue due durable scheduled tasks."""
    scheduler = get_retry_scheduler()
    return await scheduler.process_due_tasks(limit=100)


async def recover_stale_durable_orchestrations(_ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron: recover stuck orchestrations."""
    manager = get_resumable_workflow_manager()
    return await manager.recover_stale(limit=50)
