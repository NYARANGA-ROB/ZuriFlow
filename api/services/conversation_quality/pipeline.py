"""End-to-end conversation quality evaluation pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.constants import CONVERSATION_QUALITY_ENABLED
from api.db import db_client
from api.services.conversation_quality.metrics import build_evaluation_context
from api.services.conversation_quality.regression import get_regression_detector
from api.services.conversation_quality.scoring_engine import get_scoring_engine
from api.services.conversation_quality.types import (
    EVALUATION_MODEL_VERSION,
    ConversationEvaluation,
)


class ConversationQualityPipeline:
    async def evaluate_workflow_run(
        self,
        workflow_run_id: int,
        *,
        persist: bool = True,
    ) -> dict[str, Any] | None:
        if not CONVERSATION_QUALITY_ENABLED:
            return None

        run = await db_client.get_workflow_run_by_id(workflow_run_id)
        if not run or not run.is_completed:
            logger.debug("skip CQ eval: run {} missing or incomplete", workflow_run_id)
            return None

        workflow = run.workflow
        if not workflow or not workflow.organization_id:
            return None

        org_id = workflow.organization_id
        context = build_evaluation_context(run)
        if not context.get("events") and not context.get("gathered_context"):
            logger.debug("skip CQ eval: run {} has no evaluable signals", workflow_run_id)
            return None

        engine = get_scoring_engine()
        dimensions = engine.score_all(context)
        overall = engine.overall_score(dimensions)
        flags: list[str] = []
        for dim in dimensions:
            flags.extend(dim.flags)

        evaluation = ConversationEvaluation(
            organization_id=org_id,
            workflow_run_id=workflow_run_id,
            workflow_id=run.workflow_id,
            model_version=EVALUATION_MODEL_VERSION,
            overall_score=overall,
            dimensions=dimensions,
            metrics={
                "call_metrics": context.get("call_metrics"),
                "interruptions": context.get("interruptions"),
                "negotiation_outcome": context.get("negotiation_outcome"),
                "payment_collected": context.get("payment_collected"),
                "escalated": context.get("escalated"),
            },
            flags=sorted(set(flags)),
        )

        regression = await get_regression_detector().analyze(evaluation)
        evaluation.regression = regression
        if regression.get("regression_detected"):
            evaluation.flags.append("quality_regression")

        payload = evaluation.to_dict()
        payload["evaluated_at"] = datetime.now(UTC).isoformat()

        if persist:
            await db_client.upsert_conversation_quality_evaluation(
                organization_id=org_id,
                workflow_run_id=workflow_run_id,
                workflow_id=run.workflow_id,
                model_version=EVALUATION_MODEL_VERSION,
                overall_score=overall,
                dimension_scores={
                    d.dimension.value: d.to_dict() for d in dimensions
                },
                metrics=payload["metrics"],
                regression=regression,
                flags=evaluation.flags,
                evaluated_at=datetime.now(UTC),
            )

        return payload


_pipeline: ConversationQualityPipeline | None = None


def get_conversation_quality_pipeline() -> ConversationQualityPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ConversationQualityPipeline()
    return _pipeline
