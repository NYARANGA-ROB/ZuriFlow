"""Human labeling workflow for Kenyan learning samples."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.services.kenyan_continuous_learning.types import LabelTaskStatus, LearningTarget


class LabelingWorkflow:
    async def enqueue_from_samples(self, organization_id: int, sample_ids: list[int]) -> list[int]:
        task_ids: list[int] = []
        for sample_id in sample_ids:
            sample = await db_client.get_sample(sample_id, organization_id=organization_id)
            if sample is None:
                continue
            if sample.metadata_json.get("needs_label") or sample.target in {
                LearningTarget.INTENT.value,
                LearningTarget.NORMALIZATION.value,
            }:
                task = await db_client.create_label_task(
                    organization_id=organization_id,
                    sample_id=sample_id,
                    target=sample.target,
                )
                task_ids.append(task.id)
        return task_ids

    async def submit_label(
        self,
        *,
        organization_id: int,
        task_id: int,
        label_payload: dict[str, Any],
        status: LabelTaskStatus = LabelTaskStatus.APPROVED,
        notes: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        row = await db_client.update_label_task(
            task_id,
            organization_id=organization_id,
            status=status.value,
            label_payload=label_payload,
            notes=notes,
            assigned_user_id=user_id,
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "sample_id": row.sample_id,
            "target": row.target,
            "status": row.status,
            "label_payload": row.label_payload,
        }

    async def list_tasks(
        self,
        organization_id: int,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        rows, total = await db_client.list_label_tasks(
            organization_id, status=status, limit=limit, offset=offset
        )
        return {
            "organization_id": organization_id,
            "total": total,
            "tasks": [
                {
                    "id": r.id,
                    "sample_id": r.sample_id,
                    "target": r.target,
                    "status": r.status,
                    "label_payload": r.label_payload,
                    "notes": r.notes,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }


_labeling: LabelingWorkflow | None = None


def get_labeling_workflow() -> LabelingWorkflow:
    global _labeling
    if _labeling is None:
        _labeling = LabelingWorkflow()
    return _labeling
