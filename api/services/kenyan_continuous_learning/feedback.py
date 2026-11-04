"""Operator and system feedback ingestion."""

from __future__ import annotations

from typing import Any

from api.constants import KENYAN_CONTINUOUS_LEARNING_ENABLED
from api.db import db_client
from api.services.kenyan_continuous_learning.anonymizer import anonymize_text
from api.services.kenyan_continuous_learning.labeling import get_labeling_workflow
from api.services.kenyan_continuous_learning.types import FeedbackType, LearningTarget, SampleSource


class FeedbackIngestionService:
    async def ingest(
        self,
        *,
        organization_id: int,
        feedback_type: FeedbackType,
        payload: dict[str, Any],
        user_id: int | None = None,
        sample_id: int | None = None,
    ) -> dict[str, Any]:
        if not KENYAN_CONTINUOUS_LEARNING_ENABLED:
            return {"ingested": False}

        sanitized = _sanitize_payload(payload)
        row = await db_client.ingest_feedback(
            organization_id=organization_id,
            feedback_type=feedback_type.value,
            payload=sanitized,
            sample_id=sample_id,
            user_id=user_id,
        )

        created_sample_id = None
        if feedback_type == FeedbackType.NORMALIZATION_CORRECTION:
            created_sample_id = await self._normalization_feedback(
                organization_id, sanitized
            )
        elif feedback_type == FeedbackType.INTENT_CORRECTION:
            created_sample_id = await self._intent_feedback(organization_id, sanitized)
        elif feedback_type == FeedbackType.INTERRUPTION_NOTE:
            created_sample_id = await self._interruption_feedback(
                organization_id, sanitized
            )
        elif feedback_type == FeedbackType.RANKING_OUTCOME:
            created_sample_id = await self._ranking_feedback(organization_id, sanitized)

        if created_sample_id:
            await get_labeling_workflow().enqueue_from_samples(
                organization_id, [created_sample_id]
            )

        return {
            "ingested": True,
            "feedback_id": row.id,
            "sample_id": created_sample_id or sample_id,
        }

    async def _normalization_feedback(self, org_id: int, payload: dict[str, Any]) -> int:
        sample = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.NORMALIZATION.value,
            source=SampleSource.OPERATOR_FEEDBACK.value,
            locale=payload.get("locale", "mixed"),
            payload={
                "source_text": payload.get("source_text"),
                "normalized_text": payload.get("target_text"),
            },
            metadata={"needs_label": True},
        )
        return sample.id

    async def _intent_feedback(self, org_id: int, payload: dict[str, Any]) -> int:
        sample = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.INTENT.value,
            source=SampleSource.OPERATOR_FEEDBACK.value,
            locale=payload.get("locale", "mixed"),
            payload={
                "text": payload.get("text"),
                "predicted_intent": payload.get("predicted_intent"),
                "correct_intent": payload.get("correct_intent"),
            },
            metadata={"needs_label": True},
        )
        return sample.id

    async def _interruption_feedback(self, org_id: int, payload: dict[str, Any]) -> int:
        sample = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.INTERRUPTION.value,
            source=SampleSource.OPERATOR_FEEDBACK.value,
            locale=payload.get("locale", "mixed"),
            payload=payload,
            metadata={"needs_label": True},
        )
        return sample.id

    async def _ranking_feedback(self, org_id: int, payload: dict[str, Any]) -> int:
        sample = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.RANKING.value,
            source=SampleSource.OPERATOR_FEEDBACK.value,
            locale="mixed",
            payload=payload,
            metadata={"needs_label": False},
        )
        return sample.id


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            out[key] = anonymize_text(value)
        else:
            out[key] = value
    return out


_feedback: FeedbackIngestionService | None = None


def get_feedback_ingestion_service() -> FeedbackIngestionService:
    global _feedback
    if _feedback is None:
        _feedback = FeedbackIngestionService()
    return _feedback
