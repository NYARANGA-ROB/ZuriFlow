"""Retraining orchestration for Kenyan continuous learning."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.constants import KENYAN_CONTINUOUS_LEARNING_ENABLED
from api.db import db_client
from api.services.kenyan_continuous_learning.apply import get_learning_apply_service
from api.services.kenyan_continuous_learning.data_pipeline import get_kenyan_data_pipeline
from api.services.kenyan_continuous_learning.dataset_builder import get_training_dataset_builder
from api.services.kenyan_continuous_learning.labeling import get_labeling_workflow
from api.services.kenyan_continuous_learning.types import (
    LearningTarget,
    TrainingRunStatus,
)


class RetrainingOrchestrator:
    async def start_run(
        self,
        organization_id: int,
        *,
        targets: list[str] | None = None,
        days: int = 30,
        auto_apply: bool = False,
    ) -> dict[str, Any]:
        if not KENYAN_CONTINUOUS_LEARNING_ENABLED:
            return {"started": False}

        selected = targets or [t.value for t in LearningTarget if t != LearningTarget.GENERAL]
        run = await db_client.create_training_run(
            organization_id=organization_id, targets=selected
        )

        try:
            await db_client.update_training_run(
                run.id,
                organization_id=organization_id,
                status=TrainingRunStatus.COLLECTING.value,
                started_at=datetime.now(UTC),
            )

            builder = get_training_dataset_builder()
            datasets = await builder.build(organization_id, targets=selected, days=days)

            await db_client.update_training_run(
                run.id,
                organization_id=organization_id,
                status=TrainingRunStatus.BUILDING.value,
            )

            artifacts = self._derive_artifacts(datasets.get("datasets") or {})
            artifacts["export_paths"] = datasets.get("export_paths") or {}

            status = TrainingRunStatus.COMPLETED.value
            if auto_apply:
                await get_learning_apply_service().apply_artifacts(
                    organization_id,
                    artifacts,
                    apply_dictionary=True,
                    apply_ranking=True,
                )
                status = TrainingRunStatus.APPLIED.value

            await db_client.update_training_run(
                run.id,
                organization_id=organization_id,
                status=status,
                artifacts=artifacts,
                completed_at=datetime.now(UTC),
            )
            return {
                "training_run_id": run.id,
                "status": status,
                "artifacts": artifacts,
            }
        except Exception as e:
            logger.error("Kenyan CL training run {} failed: {}", run.id, e)
            await db_client.update_training_run(
                run.id,
                organization_id=organization_id,
                status=TrainingRunStatus.FAILED.value,
                error_message=str(e),
                completed_at=datetime.now(UTC),
            )
            raise

    async def collect_recent_runs(
        self, organization_id: int, workflow_run_ids: list[int]
    ) -> dict[str, Any]:
        pipeline = get_kenyan_data_pipeline()
        all_sample_ids: list[int] = []
        for run_id in workflow_run_ids:
            ids = await pipeline.collect_from_workflow_run(run_id)
            all_sample_ids.extend(ids)
        task_ids = await get_labeling_workflow().enqueue_from_samples(
            organization_id, all_sample_ids
        )
        return {"samples": len(all_sample_ids), "label_tasks": len(task_ids)}

    def _derive_artifacts(self, datasets: dict[str, Any]) -> dict[str, Any]:
        artifacts: dict[str, Any] = {}

        norm_rows = (datasets.get(LearningTarget.NORMALIZATION.value) or {}).get("rows") or []
        patches = []
        for row in norm_rows:
            source = str(row.get("source", "")).strip().lower()
            target = str(row.get("target", "")).strip()
            if not source or not target:
                continue
            kind = "phrase" if " " in source else "token"
            patches.append({"source": source, "target": target, "kind": kind, "tags": ["learned"]})
        artifacts[LearningTarget.NORMALIZATION.value] = {
            "dictionary_patches": patches[:200],
            "row_count": len(norm_rows),
        }

        intent_rows = (datasets.get(LearningTarget.INTENT.value) or {}).get("rows") or []
        intent_counter: Counter[str] = Counter()
        patterns = []
        for row in intent_rows:
            text = str(row.get("text", "")).lower()
            intent = row.get("intent")
            if not text or not intent:
                continue
            for token in text.split()[:3]:
                if len(token) >= 4:
                    patterns.append(
                        {"phrase": token, "intent": intent, "weight": 0.75, "language": "mixed"}
                    )
                    intent_counter[intent] += 1
        artifacts[LearningTarget.INTENT.value] = {
            "patterns": patterns[:300],
            "intent_distribution": dict(intent_counter),
        }

        interruption_rows = (datasets.get(LearningTarget.INTERRUPTION.value) or {}).get("rows") or []
        total = sum(int(r.get("total_interruptions") or 0) for r in interruption_rows)
        handled = sum(int(r.get("handled_within_3s") or 0) for r in interruption_rows)
        rate = (handled / total) if total else None
        artifacts[LearningTarget.INTERRUPTION.value] = {
            "recommendations": (
                ["tighten_interrupt_acknowledgment"]
                if rate is not None and rate < 0.6
                else []
            ),
            "handled_rate": rate,
        }

        ranking_rows = (datasets.get(LearningTarget.RANKING.value) or {}).get("rows") or []
        if ranking_rows:
            success = sum(1 for r in ranking_rows if float(r.get("label") or 0) >= 1.0)
            rate = success / len(ranking_rows)
            artifacts[LearningTarget.RANKING.value] = {
                "success_rate": round(rate, 4),
                "weights": {
                    "payment": min(0.45, 0.35 + rate * 0.1),
                    "answer_rate": 0.30,
                    "engagement": 0.20,
                    "escalation_penalty": 0.15,
                    "failure_penalty": 0.10,
                },
            }

        return artifacts


_orchestrator: RetrainingOrchestrator | None = None


def get_retraining_orchestrator() -> RetrainingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RetrainingOrchestrator()
    return _orchestrator
