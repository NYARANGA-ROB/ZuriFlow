"""Tests for automated conversation quality evaluation."""

from __future__ import annotations

from pipecat.utils.enums import RealtimeFeedbackType

from api.services.conversation_quality.metrics import (
    build_evaluation_context,
    collect_qa_tags,
)
from api.services.conversation_quality.scoring_engine import get_scoring_engine
from api.services.conversation_quality.types import QualityDimension


class _FakeRun:
    def __init__(self):
        self.usage_info = {"call_duration_seconds": 120}
        self.gathered_context = {
            "debt_collection": {
                "negotiation_outcome": "accepted",
                "escalated": False,
            }
        }
        self.initial_context = {}
        self.logs = {
            "realtime_feedback_events": [
                {
                    "type": RealtimeFeedbackType.BOT_STARTED_SPEAKING.value,
                    "timestamp": "2026-01-01T10:00:00+00:00",
                    "payload": {},
                },
                {
                    "type": RealtimeFeedbackType.USER_TRANSCRIPTION.value,
                    "timestamp": "2026-01-01T10:00:01+00:00",
                    "payload": {"text": "Hello", "final": True},
                },
                {
                    "type": RealtimeFeedbackType.BOT_STOPPED_SPEAKING.value,
                    "timestamp": "2026-01-01T10:00:02+00:00",
                    "payload": {},
                },
                {
                    "type": RealtimeFeedbackType.BOT_TEXT.value,
                    "timestamp": "2026-01-01T10:00:03+00:00",
                    "payload": {"text": "How can I help you today?"},
                },
                {
                    "type": RealtimeFeedbackType.TTFB_METRIC.value,
                    "timestamp": "2026-01-01T10:00:03+00:00",
                    "payload": {"ttfb_seconds": 0.5},
                },
            ]
        }
        self.annotations = {
            "qa_1": {
                "node_results": {
                    "whole_call": {
                        "tags": [],
                        "score": 8,
                    }
                }
            }
        }


def test_build_evaluation_context_extracts_signals():
    ctx = build_evaluation_context(_FakeRun())
    assert ctx["negotiation_outcome"] == "accepted"
    assert len(ctx["bot_utterances"]) == 1
    assert ctx["interruptions"]["total"] == 1


def test_scoring_engine_all_dimensions():
    ctx = build_evaluation_context(_FakeRun())
    engine = get_scoring_engine()
    dims = engine.score_all(ctx)
    assert len(dims) == 6
    keys = {d.dimension for d in dims}
    assert QualityDimension.LATENCY in keys


def test_payment_negotiation_high_on_success():
    ctx = build_evaluation_context(_FakeRun())
    score = get_scoring_engine().score_payment_negotiation(ctx)
    assert score.score >= 90


def test_interruption_handling_scores_barge_in_recovery():
    ctx = build_evaluation_context(_FakeRun())
    score = get_scoring_engine().score_interruption_handling(ctx)
    assert score.score >= 80


def test_collect_qa_tags_from_annotations():
    tags = collect_qa_tags(_FakeRun().annotations)
    assert tags == []


def test_overall_score_weighted():
    engine = get_scoring_engine()
    ctx = build_evaluation_context(_FakeRun())
    dims = engine.score_all(ctx)
    overall = engine.overall_score(dims)
    assert 0 <= overall <= 100
