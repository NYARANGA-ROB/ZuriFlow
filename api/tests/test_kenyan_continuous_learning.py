"""Tests for Kenyan continuous learning pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from api.services.kenyan_continuous_learning.anonymizer import (
    anonymize_text,
    anonymize_turns,
    hash_run_reference,
)
from api.services.kenyan_continuous_learning.orchestrator import RetrainingOrchestrator
from api.services.kenyan_continuous_learning.types import LearningTarget


def test_anonymize_text_redacts_phone_and_email():
    text = "Call me on 0712345678 or email john@example.com"
    out = anonymize_text(text)
    assert "[PHONE]" in out
    assert "[EMAIL]" in out
    assert "0712345678" not in out
    assert "john@example.com" not in out


def test_anonymize_turns_preserves_structure():
    turns = [{"speaker": "user", "text": "Nipe 254712345678", "timestamp": "t1"}]
    out = anonymize_turns(turns)
    assert out[0]["speaker"] == "user"
    assert "[PHONE]" in out[0]["text"]


def test_hash_run_reference_is_stable():
    assert hash_run_reference(42, 7) == hash_run_reference(42, 7)
    assert hash_run_reference(42, 7) != hash_run_reference(43, 7)


def test_orchestrator_derives_normalization_artifacts():
    orch = RetrainingOrchestrator()
    artifacts = orch._derive_artifacts(
        {
            LearningTarget.NORMALIZATION.value: {
                "rows": [
                    {"source": "msee", "target": "person"},
                    {"source": "nipe pesa", "target": "send money"},
                ]
            }
        }
    )
    patches = artifacts[LearningTarget.NORMALIZATION.value]["dictionary_patches"]
    assert len(patches) == 2
    kinds = {p["kind"] for p in patches}
    assert kinds == {"token", "phrase"}


def test_orchestrator_derives_intent_artifacts():
    orch = RetrainingOrchestrator()
    artifacts = orch._derive_artifacts(
        {
            LearningTarget.INTENT.value: {
                "rows": [
                    {"text": "nataka kulipa deni", "intent": "payment_intent"},
                ]
            }
        }
    )
    patterns = artifacts[LearningTarget.INTENT.value]["patterns"]
    assert patterns
    assert patterns[0]["intent"] == "payment_intent"


def test_orchestrator_interruption_recommendation_when_low_handled_rate():
    orch = RetrainingOrchestrator()
    artifacts = orch._derive_artifacts(
        {
            LearningTarget.INTERRUPTION.value: {
                "rows": [
                    {"total_interruptions": 10, "handled_within_3s": 2},
                ]
            }
        }
    )
    interruption = artifacts[LearningTarget.INTERRUPTION.value]
    assert interruption["handled_rate"] == 0.2
    assert "tighten_interrupt_acknowledgment" in interruption["recommendations"]


def test_orchestrator_ranking_weights_from_success_rate():
    orch = RetrainingOrchestrator()
    artifacts = orch._derive_artifacts(
        {
            LearningTarget.RANKING.value: {
                "rows": [
                    {"label": 1.0},
                    {"label": 0.0},
                ]
            }
        }
    )
    ranking = artifacts[LearningTarget.RANKING.value]
    assert ranking["success_rate"] == 0.5
    assert "payment" in ranking["weights"]


def test_dataset_builder_writes_jsonl_exports(tmp_path, monkeypatch):
    from api.services.kenyan_continuous_learning.dataset_builder import TrainingDatasetBuilder

    monkeypatch.setattr(
        "api.services.kenyan_continuous_learning.dataset_builder.KENYAN_CL_DATA_PATH",
        str(tmp_path),
    )
    builder = TrainingDatasetBuilder()
    datasets = {
        LearningTarget.NORMALIZATION.value: {
            "rows": [{"source": "msee", "target": "person"}],
        }
    }
    paths = builder._write_exports(99, datasets)
    path = Path(paths[LearningTarget.NORMALIZATION.value])
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "msee" in lines[0]


@pytest.mark.asyncio
async def test_data_pipeline_skips_incomplete_run():
    from api.services.kenyan_continuous_learning.data_pipeline import KenyanDataPipeline

    pipeline = KenyanDataPipeline()
    with patch("api.services.kenyan_continuous_learning.data_pipeline.db_client") as mock_db:
        run = AsyncMock()
        run.is_completed = False
        mock_db.get_workflow_run_by_id = AsyncMock(return_value=run)
        assert await pipeline.collect_from_workflow_run(1) == []


@pytest.mark.asyncio
async def test_feedback_ingestion_creates_normalization_sample():
    from api.services.kenyan_continuous_learning.feedback import FeedbackIngestionService
    from api.services.kenyan_continuous_learning.types import FeedbackType

    svc = FeedbackIngestionService()
    sample = AsyncMock()
    sample.id = 10
    with (
        patch("api.services.kenyan_continuous_learning.feedback.db_client") as mock_db,
        patch(
            "api.services.kenyan_continuous_learning.feedback.get_labeling_workflow"
        ) as mock_labeling,
    ):
        mock_db.ingest_feedback = AsyncMock(return_value=AsyncMock(id=1))
        mock_db.create_kenyan_learning_sample = AsyncMock(return_value=sample)
        mock_labeling.return_value.enqueue_from_samples = AsyncMock(return_value=[5])
        result = await svc.ingest(
            organization_id=1,
            feedback_type=FeedbackType.NORMALIZATION_CORRECTION,
            payload={"source_text": "msee", "target_text": "person"},
            user_id=2,
        )
    assert result["sample_id"] == 10
    mock_labeling.return_value.enqueue_from_samples.assert_awaited_once_with(1, [10])
