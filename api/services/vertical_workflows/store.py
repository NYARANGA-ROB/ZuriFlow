"""Persistence for vertical workflow instances."""

from __future__ import annotations

import time
import uuid
from typing import Any

from api.services.vertical_workflows.schema import VerticalWorkflowInstance, WorkflowInstanceStatus


class VerticalWorkflowStore:
    """In-memory store with optional workflow_run gathered_context persistence."""

    def __init__(self) -> None:
        self._instances: dict[str, VerticalWorkflowInstance] = {}

    def create(
        self,
        *,
        template_id: str,
        organization_id: int,
        workflow_run_id: int | None = None,
        locale: str = "en",
        variables: dict[str, Any] | None = None,
        entry_step_id: str = "",
    ) -> VerticalWorkflowInstance:
        now = time.time()
        instance = VerticalWorkflowInstance(
            instance_id=str(uuid.uuid4()),
            template_id=template_id,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            status=WorkflowInstanceStatus.RUNNING,
            current_step_id=entry_step_id,
            locale=locale,
            variables=dict(variables or {}),
            created_at=now,
            updated_at=now,
        )
        self._instances[instance.instance_id] = instance
        return instance

    def get(self, instance_id: str) -> VerticalWorkflowInstance | None:
        return self._instances.get(instance_id)

    def require(self, instance_id: str) -> VerticalWorkflowInstance:
        instance = self.get(instance_id)
        if instance is None:
            raise KeyError(f"Vertical workflow instance not found: {instance_id}")
        return instance

    def save(self, instance: VerticalWorkflowInstance) -> None:
        instance.updated_at = time.time()
        self._instances[instance.instance_id] = instance

    async def persist_to_workflow_run(self, instance: VerticalWorkflowInstance) -> None:
        if not instance.workflow_run_id:
            return
        try:
            from api.db import db_client

            run = await db_client.get_workflow_run_by_id(instance.workflow_run_id)
            if not run:
                return
            gathered = dict(run.gathered_context or {})
            gathered["vertical_workflow"] = instance.to_dict()
            await db_client.update_workflow_run(
                run_id=instance.workflow_run_id,
                gathered_context=gathered,
            )
        except Exception:
            pass

    async def load_from_workflow_run(
        self,
        workflow_run_id: int,
    ) -> VerticalWorkflowInstance | None:
        try:
            from api.db import db_client

            run = await db_client.get_workflow_run(workflow_run_id)
            if not run:
                return None
            gathered = run.gathered_context or {}
            raw = gathered.get("vertical_workflow")
            if not raw:
                return None
            instance = VerticalWorkflowInstance.from_dict(raw)
            self._instances[instance.instance_id] = instance
            return instance
        except Exception:
            return None

    def append_history(
        self,
        instance: VerticalWorkflowInstance,
        *,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        instance.history.append(
            {
                "ts": time.time(),
                "event_type": event_type,
                "payload": payload,
            }
        )


_store: VerticalWorkflowStore | None = None


def get_vertical_workflow_store() -> VerticalWorkflowStore:
    global _store
    if _store is None:
        _store = VerticalWorkflowStore()
    return _store
