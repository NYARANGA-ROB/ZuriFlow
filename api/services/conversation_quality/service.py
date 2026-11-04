"""Facade for conversation quality evaluation APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from api.constants import CONVERSATION_QUALITY_ENABLED
from api.db import db_client
from api.services.conversation_quality.pipeline import get_conversation_quality_pipeline
from api.services.conversation_quality.reporting import (
    build_org_summary,
    export_evaluation_json,
    export_summary_csv,
)
from api.services.conversation_quality.types import EVALUATION_MODEL_VERSION, QualityDimension


class ConversationQualityService:
    @property
    def enabled(self) -> bool:
        return CONVERSATION_QUALITY_ENABLED

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model_version": EVALUATION_MODEL_VERSION,
            "dimensions": [d.value for d in QualityDimension],
        }

    async def evaluate_run(
        self, workflow_run_id: int, *, persist: bool = True
    ) -> dict[str, Any] | None:
        return await get_conversation_quality_pipeline().evaluate_workflow_run(
            workflow_run_id, persist=persist
        )

    async def get_evaluation(
        self, organization_id: int, workflow_run_id: int
    ) -> dict[str, Any] | None:
        row = await db_client.get_conversation_quality_evaluation(
            workflow_run_id, organization_id=organization_id
        )
        if row is None:
            return None
        return _row_to_dict(row)

    async def list_evaluations(
        self,
        organization_id: int,
        *,
        workflow_id: int | None = None,
        days: int = 30,
        regression_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        rows, total = await db_client.list_conversation_quality_evaluations(
            organization_id,
            workflow_id=workflow_id,
            from_ts=start,
            to_ts=end,
            regression_only=regression_only,
            limit=limit,
            offset=offset,
        )
        return {
            "organization_id": organization_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "evaluations": [_row_to_dict(r) for r in rows],
        }

    async def org_summary(
        self, organization_id: int, *, days: int = 30
    ) -> dict[str, Any]:
        data = await self.list_evaluations(
            organization_id, days=days, limit=500, offset=0
        )
        evaluations = data["evaluations"]
        regressions = [
            e for e in evaluations if (e.get("regression") or {}).get("regression_detected")
        ]
        return build_org_summary(
            organization_id=organization_id,
            evaluations=evaluations,
            regressions=regressions,
        )

    def export_run_json(self, evaluation: dict[str, Any]):
        return export_evaluation_json(evaluation)

    def export_summary_csv(self, evaluations: list[dict[str, Any]]):
        return export_summary_csv(evaluations)


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "organization_id": row.organization_id,
        "workflow_run_id": row.workflow_run_id,
        "workflow_id": row.workflow_id,
        "model_version": row.model_version,
        "overall_score": row.overall_score,
        "dimensions": row.dimension_scores or {},
        "metrics": row.metrics or {},
        "regression": row.regression or {},
        "flags": row.flags or [],
        "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
    }


_service: ConversationQualityService | None = None


def get_conversation_quality_service() -> ConversationQualityService:
    global _service
    if _service is None:
        _service = ConversationQualityService()
    return _service
