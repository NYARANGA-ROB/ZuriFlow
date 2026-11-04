"""Kenyan continuous learning facade."""

from __future__ import annotations

from typing import Any

from api.constants import KENYAN_CONTINUOUS_LEARNING_ENABLED
from api.db import db_client
from api.services.kenyan_continuous_learning.apply import get_learning_apply_service
from api.services.kenyan_continuous_learning.data_pipeline import get_kenyan_data_pipeline
from api.services.kenyan_continuous_learning.feedback import get_feedback_ingestion_service
from api.services.kenyan_continuous_learning.labeling import get_labeling_workflow
from api.services.kenyan_continuous_learning.orchestrator import get_retraining_orchestrator
from api.services.kenyan_continuous_learning.types import FeedbackType, LearningTarget


class KenyanContinuousLearningService:
    @property
    def enabled(self) -> bool:
        return KENYAN_CONTINUOUS_LEARNING_ENABLED

    async def collect_run(
        self, workflow_run_id: int, *, organization_id: int | None = None
    ) -> dict[str, Any]:
        run = await db_client.get_workflow_run_by_id(workflow_run_id)
        if organization_id is not None:
            if not run or not run.workflow or run.workflow.organization_id != organization_id:
                return {"sample_ids": [], "count": 0, "not_found": True}
        ids = await get_kenyan_data_pipeline().collect_from_workflow_run(workflow_run_id)
        return {"sample_ids": ids, "count": len(ids)}

    async def ingest_feedback(
        self,
        *,
        organization_id: int,
        feedback_type: FeedbackType,
        payload: dict[str, Any],
        user_id: int | None = None,
    ) -> dict[str, Any]:
        return await get_feedback_ingestion_service().ingest(
            organization_id=organization_id,
            feedback_type=feedback_type,
            payload=payload,
            user_id=user_id,
        )

    async def list_label_tasks(self, organization_id: int, **kwargs) -> dict[str, Any]:
        return await get_labeling_workflow().list_tasks(organization_id, **kwargs)

    async def submit_label(self, organization_id: int, **kwargs) -> dict[str, Any] | None:
        return await get_labeling_workflow().submit_label(
            organization_id=organization_id, **kwargs
        )

    async def start_training(
        self, organization_id: int, *, auto_apply: bool = False, **kwargs
    ) -> dict[str, Any]:
        return await get_retraining_orchestrator().start_run(
            organization_id, auto_apply=auto_apply, **kwargs
        )

    async def apply_training_run(
        self, organization_id: int, training_run_id: int
    ) -> dict[str, Any]:
        run = await db_client.get_training_run(training_run_id, organization_id=organization_id)
        if run is None:
            return {"applied": False}
        result = await get_learning_apply_service().apply_artifacts(
            organization_id, run.artifacts or {}, apply_dictionary=True, apply_ranking=True
        )
        await db_client.update_training_run(
            training_run_id,
            organization_id=organization_id,
            status="applied",
        )
        return {"applied": True, **result}

    async def summary(self, organization_id: int, *, days: int = 30) -> dict[str, Any]:
        from datetime import UTC, datetime, timedelta

        start = datetime.now(UTC) - timedelta(days=days)
        _, sample_total = await db_client.list_kenyan_learning_samples(
            organization_id, from_ts=start, limit=1
        )
        _, pending_total = await db_client.list_label_tasks(
            organization_id, status="pending", limit=1
        )
        runs = await db_client.list_training_runs(organization_id, limit=5)
        return {
            "organization_id": organization_id,
            "enabled": self.enabled,
            "targets": [t.value for t in LearningTarget],
            "samples_recent": sample_total,
            "label_tasks_pending": pending_total,
            "training_runs": [
                {
                    "id": r.id,
                    "status": r.status,
                    "targets": r.targets,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ],
        }


_service: KenyanContinuousLearningService | None = None


def get_kenyan_continuous_learning_service() -> KenyanContinuousLearningService:
    global _service
    if _service is None:
        _service = KenyanContinuousLearningService()
    return _service
