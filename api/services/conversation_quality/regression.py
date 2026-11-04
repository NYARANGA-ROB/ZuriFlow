"""Regression detection against historical quality baselines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from api.db import db_client
from api.services.conversation_quality.types import (
    REGRESSION_DROP_THRESHOLD,
    REGRESSION_MIN_SAMPLE,
    ConversationEvaluation,
    QualityDimension,
)


class RegressionDetector:
    async def analyze(
        self,
        evaluation: ConversationEvaluation,
        *,
        window_days: int = 30,
    ) -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(days=window_days)
        baseline = await db_client.get_conversation_quality_baseline(
            evaluation.organization_id,
            workflow_id=evaluation.workflow_id,
            from_ts=start,
            to_ts=end,
            exclude_run_id=evaluation.workflow_run_id,
        )

        sample_size = int(baseline.get("sample_size") or 0)
        if sample_size < REGRESSION_MIN_SAMPLE:
            return {
                "regression_detected": False,
                "reason": "insufficient_baseline",
                "baseline_sample_size": sample_size,
                "baseline_overall": baseline.get("avg_overall"),
            }

        baseline_overall = float(baseline.get("avg_overall") or 0.0)
        drop = baseline_overall - evaluation.overall_score
        dimension_regressions: dict[str, Any] = {}

        baseline_dims = baseline.get("dimension_averages") or {}
        for dim in evaluation.dimensions:
            key = dim.dimension.value
            base_val = baseline_dims.get(key)
            if base_val is None:
                continue
            dim_drop = float(base_val) - dim.score
            if dim_drop >= REGRESSION_DROP_THRESHOLD:
                dimension_regressions[key] = {
                    "baseline": round(float(base_val), 2),
                    "current": dim.score,
                    "drop": round(dim_drop, 2),
                }

        regression = drop >= REGRESSION_DROP_THRESHOLD or bool(dimension_regressions)
        return {
            "regression_detected": regression,
            "baseline_sample_size": sample_size,
            "baseline_overall": round(baseline_overall, 2),
            "current_overall": round(evaluation.overall_score, 2),
            "overall_drop": round(drop, 2),
            "dimension_regressions": dimension_regressions,
            "window_days": window_days,
        }


_detector: RegressionDetector | None = None


def get_regression_detector() -> RegressionDetector:
    global _detector
    if _detector is None:
        _detector = RegressionDetector()
    return _detector
