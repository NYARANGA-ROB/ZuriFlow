"""Build training datasets from labeled Kenyan conversation samples."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from api.constants import KENYAN_CL_DATA_PATH
from api.db import db_client
from api.services.kenyan_continuous_learning.types import LabelTaskStatus, LearningTarget


class TrainingDatasetBuilder:
    async def build(
        self,
        organization_id: int,
        *,
        targets: list[str] | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        selected = targets or [t.value for t in LearningTarget]

        datasets: dict[str, Any] = {}
        for target in selected:
            if target == LearningTarget.NORMALIZATION.value:
                datasets[target] = await self._build_normalization(organization_id, start)
            elif target == LearningTarget.INTENT.value:
                datasets[target] = await self._build_intent(organization_id, start)
            elif target == LearningTarget.INTERRUPTION.value:
                datasets[target] = await self._build_interruption(organization_id, start)
            elif target == LearningTarget.RANKING.value:
                datasets[target] = await self._build_ranking(organization_id, start)

        export_paths = self._write_exports(organization_id, datasets)
        return {
            "organization_id": organization_id,
            "from_ts": start.isoformat(),
            "to_ts": end.isoformat(),
            "datasets": datasets,
            "export_paths": export_paths,
        }

    async def _build_normalization(self, org_id: int, start: datetime) -> dict[str, Any]:
        samples, _ = await db_client.list_kenyan_learning_samples(
            org_id, target=LearningTarget.NORMALIZATION.value, from_ts=start, limit=5000
        )
        tasks, _ = await db_client.list_label_tasks(
            org_id, status=LabelTaskStatus.APPROVED.value, limit=5000
        )
        approved_by_sample = {t.sample_id: t.label_payload for t in tasks}

        rows: list[dict[str, str]] = []
        for sample in samples:
            payload = sample.payload or {}
            label = approved_by_sample.get(sample.id) or {}
            source = label.get("source_text") or payload.get("source_text")
            target = label.get("target_text") or payload.get("normalized_text")
            if source and target and source != target:
                rows.append({"source": source, "target": target, "locale": sample.locale})

        return {"row_count": len(rows), "rows": rows[:500]}

    async def _build_intent(self, org_id: int, start: datetime) -> dict[str, Any]:
        samples, _ = await db_client.list_kenyan_learning_samples(
            org_id, target=LearningTarget.INTENT.value, from_ts=start, limit=5000
        )
        tasks, _ = await db_client.list_label_tasks(
            org_id, status=LabelTaskStatus.APPROVED.value, limit=5000
        )
        approved_by_sample = {t.sample_id: t.label_payload for t in tasks}

        rows: list[dict[str, Any]] = []
        for sample in samples:
            payload = sample.payload or {}
            label = approved_by_sample.get(sample.id) or {}
            text = label.get("text") or payload.get("text")
            intent = label.get("intent") or payload.get("predicted_intent")
            if text and intent:
                rows.append({"text": text, "intent": intent, "locale": sample.locale})
        return {"row_count": len(rows), "rows": rows[:500]}

    async def _build_interruption(self, org_id: int, start: datetime) -> dict[str, Any]:
        samples, _ = await db_client.list_kenyan_learning_samples(
            org_id, target=LearningTarget.INTERRUPTION.value, from_ts=start, limit=2000
        )
        rows = []
        for sample in samples:
            payload = sample.payload or {}
            interruptions = payload.get("interruptions") or {}
            rows.append(
                {
                    "turns": payload.get("turns") or [],
                    "total_interruptions": interruptions.get("total", 0),
                    "handled_within_3s": interruptions.get("handled_within_3s", 0),
                }
            )
        return {"row_count": len(rows), "rows": rows[:200]}

    async def _build_ranking(self, org_id: int, start: datetime) -> dict[str, Any]:
        samples, _ = await db_client.list_kenyan_learning_samples(
            org_id, target=LearningTarget.RANKING.value, from_ts=start, limit=5000
        )
        rows = []
        for sample in samples:
            payload = sample.payload or {}
            collected = bool(payload.get("payment_collected"))
            rows.append(
                {
                    "label": 1.0 if collected else 0.0,
                    "negotiation_outcome": payload.get("negotiation_outcome"),
                    "call_duration_seconds": payload.get("call_duration_seconds"),
                }
            )
        return {"row_count": len(rows), "rows": rows[:500]}

    def _write_exports(self, org_id: int, datasets: dict[str, Any]) -> dict[str, str]:
        base = Path(KENYAN_CL_DATA_PATH) / f"org_{org_id}"
        base.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        for target, data in datasets.items():
            path = base / f"{target}_{stamp}.jsonl"
            with path.open("w", encoding="utf-8") as fh:
                for row in data.get("rows") or []:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            paths[target] = str(path)
        return paths


_builder: TrainingDatasetBuilder | None = None


def get_training_dataset_builder() -> TrainingDatasetBuilder:
    global _builder
    if _builder is None:
        _builder = TrainingDatasetBuilder()
    return _builder
