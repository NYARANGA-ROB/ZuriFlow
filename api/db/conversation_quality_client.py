"""Database operations for conversation quality evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert

from api.db.base_client import BaseDBClient
from api.db.models import ConversationQualityEvaluationModel


class ConversationQualityClient(BaseDBClient):
    async def upsert_conversation_quality_evaluation(
        self,
        *,
        organization_id: int,
        workflow_run_id: int,
        workflow_id: int | None,
        model_version: str,
        overall_score: float,
        dimension_scores: dict[str, Any],
        metrics: dict[str, Any],
        regression: dict[str, Any],
        flags: list[str],
        evaluated_at: datetime | None = None,
    ) -> ConversationQualityEvaluationModel:
        from datetime import UTC

        ts = evaluated_at or datetime.now(UTC)
        async with self.async_session() as session:
            stmt = (
                insert(ConversationQualityEvaluationModel)
                .values(
                    organization_id=organization_id,
                    workflow_run_id=workflow_run_id,
                    workflow_id=workflow_id,
                    model_version=model_version,
                    overall_score=overall_score,
                    dimension_scores=dimension_scores,
                    metrics=metrics,
                    regression=regression,
                    flags=flags,
                    evaluated_at=ts,
                )
                .on_conflict_do_update(
                    index_elements=["workflow_run_id"],
                    set_={
                        "model_version": model_version,
                        "overall_score": overall_score,
                        "dimension_scores": dimension_scores,
                        "metrics": metrics,
                        "regression": regression,
                        "flags": flags,
                        "evaluated_at": ts,
                    },
                )
                .returning(ConversationQualityEvaluationModel)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one()

    async def get_conversation_quality_evaluation(
        self,
        workflow_run_id: int,
        *,
        organization_id: int,
    ) -> ConversationQualityEvaluationModel | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(ConversationQualityEvaluationModel).where(
                    ConversationQualityEvaluationModel.workflow_run_id == workflow_run_id,
                    ConversationQualityEvaluationModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def list_conversation_quality_evaluations(
        self,
        organization_id: int,
        *,
        workflow_id: int | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        regression_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ConversationQualityEvaluationModel], int]:
        async with self.async_session() as session:
            filters = [
                ConversationQualityEvaluationModel.organization_id == organization_id
            ]
            if workflow_id is not None:
                filters.append(
                    ConversationQualityEvaluationModel.workflow_id == workflow_id
                )
            if from_ts is not None:
                filters.append(
                    ConversationQualityEvaluationModel.evaluated_at >= from_ts
                )
            if to_ts is not None:
                filters.append(
                    ConversationQualityEvaluationModel.evaluated_at <= to_ts
                )

            base = select(ConversationQualityEvaluationModel).where(*filters)
            result = await session.execute(
                base.order_by(desc(ConversationQualityEvaluationModel.evaluated_at))
            )
            rows = list(result.scalars().all())
            if regression_only:
                rows = [
                    r
                    for r in rows
                    if (r.regression or {}).get("regression_detected") is True
                ]
            total = len(rows)
            page = rows[offset : offset + limit]
            return page, total

    async def get_conversation_quality_baseline(
        self,
        organization_id: int,
        *,
        workflow_id: int | None,
        from_ts: datetime,
        to_ts: datetime,
        exclude_run_id: int | None = None,
    ) -> dict[str, Any]:
        async with self.async_session() as session:
            filters = [
                ConversationQualityEvaluationModel.organization_id == organization_id,
                ConversationQualityEvaluationModel.evaluated_at >= from_ts,
                ConversationQualityEvaluationModel.evaluated_at <= to_ts,
            ]
            if workflow_id is not None:
                filters.append(
                    ConversationQualityEvaluationModel.workflow_id == workflow_id
                )
            if exclude_run_id is not None:
                filters.append(
                    ConversationQualityEvaluationModel.workflow_run_id != exclude_run_id
                )

            result = await session.execute(
                select(
                    func.count(ConversationQualityEvaluationModel.id),
                    func.avg(ConversationQualityEvaluationModel.overall_score),
                ).where(*filters)
            )
            count, avg_overall = result.one()
            sample_size = int(count or 0)
            if sample_size == 0:
                return {"sample_size": 0, "avg_overall": None, "dimension_averages": {}}

            rows = await session.execute(
                select(ConversationQualityEvaluationModel.dimension_scores).where(*filters)
            )
            dim_sums: dict[str, list[float]] = {}
            for (scores,) in rows.all():
                if not isinstance(scores, dict):
                    continue
                for key, data in scores.items():
                    if isinstance(data, dict) and data.get("score") is not None:
                        dim_sums.setdefault(key, []).append(float(data["score"]))

            return {
                "sample_size": sample_size,
                "avg_overall": float(avg_overall or 0.0),
                "dimension_averages": {
                    k: sum(v) / len(v) for k, v in dim_sums.items() if v
                },
            }
