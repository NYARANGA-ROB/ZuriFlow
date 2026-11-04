"""Apply approved learning artifacts to runtime Kenyan models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from api.constants import KENYAN_CL_DATA_PATH
from api.enums import OrganizationConfigurationKey
from api.services.call_prioritization.config import CallPrioritizationConfig
from api.services.kenyan_continuous_learning.types import LearningTarget
from api.services.kenyan_normalize.service import get_kenyan_normalize_service


class LearningApplyService:
    async def apply_artifacts(
        self,
        organization_id: int,
        artifacts: dict[str, Any],
        *,
        apply_dictionary: bool = True,
        apply_ranking: bool = False,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {"organization_id": organization_id}

        if apply_dictionary:
            norm = artifacts.get(LearningTarget.NORMALIZATION.value) or {}
            applied = self._apply_normalization_patches(norm.get("dictionary_patches") or [])
            results["normalization_applied"] = applied

        intent = artifacts.get(LearningTarget.INTENT.value) or {}
        intent_path = self._write_intent_learned(organization_id, intent.get("patterns") or [])
        results["intent_patterns_path"] = intent_path

        if apply_ranking:
            ranking = artifacts.get(LearningTarget.RANKING.value) or {}
            updated = await self._apply_ranking_weights(organization_id, ranking.get("weights"))
            results["ranking_config_updated"] = updated

        interruption = artifacts.get(LearningTarget.INTERRUPTION.value) or {}
        results["interruption_notes"] = interruption.get("recommendations") or []

        return results

    def _apply_normalization_patches(self, patches: list[dict[str, Any]]) -> int:
        svc = get_kenyan_normalize_service()
        if not svc.enabled:
            return 0
        count = 0
        for patch in patches:
            source = patch.get("source")
            target = patch.get("target")
            if not source or not target:
                continue
            kind = patch.get("kind", "token")
            if kind == "phrase":
                svc.add_phrase(source, target, tags=patch.get("tags"))
            else:
                svc.add_token(source, target, tags=patch.get("tags"))
            count += 1
        if count:
            svc.dictionary.reload()
        from api.services.kenyan_intent.learned_patterns import invalidate_learned_pattern_cache

        invalidate_learned_pattern_cache()
        return count

    def _write_intent_learned(
        self, organization_id: int, patterns: list[dict[str, Any]]
    ) -> str | None:
        if not patterns:
            return None
        base = Path(KENYAN_CL_DATA_PATH) / f"org_{organization_id}"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "intent_learned_patterns.json"
        path.write_text(json.dumps({"patterns": patterns}, indent=2), encoding="utf-8")
        return str(path)

    async def _apply_ranking_weights(
        self, organization_id: int, weights: dict[str, float] | None
    ) -> bool:
        if not weights:
            return False
        from api.db import db_client

        row = await db_client.get_configuration(
            organization_id,
            OrganizationConfigurationKey.CALL_PRIORITIZATION_CONFIGURATION.value,
        )
        raw = dict(row.value) if row and row.value else {}
        cfg = CallPrioritizationConfig.from_dict(raw)
        merged = {
            "payment": weights.get("payment", cfg.weights.payment),
            "answer_rate": weights.get("answer_rate", cfg.weights.answer_rate),
            "engagement": weights.get("engagement", cfg.weights.engagement),
            "escalation_penalty": weights.get(
                "escalation_penalty", cfg.weights.escalation_penalty
            ),
            "failure_penalty": weights.get("failure_penalty", cfg.weights.failure_penalty),
        }
        raw["weights"] = merged
        raw["learned_weights"] = merged
        await db_client.upsert_configuration(
            organization_id,
            OrganizationConfigurationKey.CALL_PRIORITIZATION_CONFIGURATION.value,
            raw,
        )
        logger.info("Applied learned ranking weights for org {}", organization_id)
        return True


_apply: LearningApplyService | None = None


def get_learning_apply_service() -> LearningApplyService:
    global _apply
    if _apply is None:
        _apply = LearningApplyService()
    return _apply
