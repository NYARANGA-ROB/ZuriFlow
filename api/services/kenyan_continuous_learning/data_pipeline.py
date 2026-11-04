"""Collect anonymized Kenyan conversation samples from completed runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger
from pipecat.utils.enums import RealtimeFeedbackType

from api.constants import KENYAN_CONTINUOUS_LEARNING_ENABLED
from api.db import db_client
from api.services.conversation_quality.metrics import build_evaluation_context
from api.services.kenyan_continuous_learning.anonymizer import (
    anonymize_text,
    anonymize_turns,
    hash_run_reference,
)
from api.services.kenyan_continuous_learning.types import LearningTarget, SampleSource
from api.services.kenyan_intent.service import get_realtime_intent_service
from api.services.kenyan_normalize.service import get_kenyan_normalize_service


class KenyanDataPipeline:
    async def collect_from_workflow_run(self, workflow_run_id: int) -> list[int]:
        if not KENYAN_CONTINUOUS_LEARNING_ENABLED:
            return []

        run = await db_client.get_workflow_run_by_id(workflow_run_id)
        if not run or not run.workflow or not run.is_completed:
            return []

        org_id = run.workflow.organization_id
        ctx = build_evaluation_context(run)
        events = ctx.get("events") or []
        if not events:
            return []

        turns = _extract_turns(events)
        if not turns:
            return []

        run_hash = hash_run_reference(workflow_run_id, org_id)
        created_ids: list[int] = []

        general = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.GENERAL.value,
            source=SampleSource.WORKFLOW_RUN.value,
            run_reference_hash=run_hash,
            locale=_detect_locale(turns),
            payload={
                "turns": anonymize_turns(turns),
                "metrics": ctx.get("call_metrics"),
                "interruptions": ctx.get("interruptions"),
            },
            metadata={"workflow_id": run.workflow_id},
        )
        created_ids.append(general.id)

        for turn in turns:
            if turn.get("speaker") != "user":
                continue
            text = str(turn.get("text") or "")
            if not text.strip():
                continue
            await self._maybe_create_normalization_sample(org_id, run_hash, text, created_ids)
            await self._maybe_create_intent_sample(org_id, run_hash, text, created_ids)

        interruption = ctx.get("interruptions") or {}
        if int(interruption.get("total") or 0) > 0:
            row = await db_client.create_kenyan_learning_sample(
                organization_id=org_id,
                target=LearningTarget.INTERRUPTION.value,
                source=SampleSource.WORKFLOW_RUN.value,
                run_reference_hash=run_hash,
                locale=_detect_locale(turns),
                payload={
                    "turns": anonymize_turns(turns[-6:]),
                    "interruptions": interruption,
                },
                metadata={"workflow_id": run.workflow_id},
            )
            created_ids.append(row.id)

        if ctx.get("negotiation_outcome") or ctx.get("payment_collected"):
            row = await db_client.create_kenyan_learning_sample(
                organization_id=org_id,
                target=LearningTarget.RANKING.value,
                source=SampleSource.WORKFLOW_RUN.value,
                run_reference_hash=run_hash,
                locale=_detect_locale(turns),
                payload={
                    "negotiation_outcome": ctx.get("negotiation_outcome"),
                    "payment_collected": ctx.get("payment_collected"),
                    "disposition": ctx.get("disposition"),
                    "call_duration_seconds": (ctx.get("call_metrics") or {}).get(
                        "call_duration_seconds"
                    ),
                },
                metadata={"workflow_id": run.workflow_id},
            )
            created_ids.append(row.id)

        logger.debug(
            "Kenyan CL collected {} samples for run {}",
            len(created_ids),
            workflow_run_id,
        )
        return created_ids

    async def _maybe_create_normalization_sample(
        self,
        org_id: int,
        run_hash: str,
        text: str,
        created_ids: list[int],
    ) -> None:
        svc = get_kenyan_normalize_service()
        if not svc.enabled:
            return
        result = svc.normalize(text)
        if result.normalized == result.original:
            return
        row = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.NORMALIZATION.value,
            source=SampleSource.WORKFLOW_RUN.value,
            run_reference_hash=run_hash,
            locale="mixed",
            payload={
                "source_text": anonymize_text(result.original),
                "normalized_text": anonymize_text(result.normalized),
                "mappings": [
                    {
                        "original": m.original,
                        "normalized": m.normalized,
                        "source": m.source.value,
                        "confidence": m.confidence,
                    }
                    for m in result.mappings
                ],
            },
            metadata={"auto_normalized": True},
        )
        created_ids.append(row.id)

    async def _maybe_create_intent_sample(
        self,
        org_id: int,
        run_hash: str,
        text: str,
        created_ids: list[int],
    ) -> None:
        svc = get_realtime_intent_service()
        if not svc.enabled:
            return
        result = svc._classifier.classify(text)  # noqa: SLF001
        if result.confidence >= 0.85:
            return
        row = await db_client.create_kenyan_learning_sample(
            organization_id=org_id,
            target=LearningTarget.INTENT.value,
            source=SampleSource.INTENT_LOW_CONFIDENCE.value,
            run_reference_hash=run_hash,
            locale=result.language,
            payload={
                "text": anonymize_text(text),
                "predicted_intent": result.intent.value,
                "confidence": result.confidence,
                "matched_phrases": result.matched_phrases,
                "normalized_text": anonymize_text(result.normalized_text or ""),
            },
            metadata={"needs_label": True},
        )
        created_ids.append(row.id)


def _extract_turns(events: list[dict]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for event in events:
        etype = event.get("type")
        payload = event.get("payload") or {}
        if etype == RealtimeFeedbackType.USER_TRANSCRIPTION.value and payload.get("final"):
            turns.append(
                {
                    "speaker": "user",
                    "text": payload.get("text", ""),
                    "timestamp": event.get("timestamp"),
                }
            )
        elif etype == RealtimeFeedbackType.BOT_TEXT.value:
            turns.append(
                {
                    "speaker": "assistant",
                    "text": payload.get("text", ""),
                    "timestamp": event.get("timestamp"),
                }
            )
    return turns


def _detect_locale(turns: list[dict]) -> str:
    sw_markers = ("sawa", "habari", "asante", "ndio", "pole", "lipa", "miadi")
    joined = " ".join(str(t.get("text", "")).lower() for t in turns)
    if any(m in joined for m in sw_markers):
        return "mixed"
    return "en"


_pipeline: KenyanDataPipeline | None = None


def get_kenyan_data_pipeline() -> KenyanDataPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = KenyanDataPipeline()
    return _pipeline
