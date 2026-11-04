"""Latency SLO, correlation, tenant cache, and pipeline stage percentiles."""

from __future__ import annotations

import pytest

from api.services.realtime_observability.correlation import (
    CallCorrelation,
    bind_call_correlation,
    get_call_id,
)
from api.services.realtime_observability.percentiles import (
    record_stage_ms,
    reset_for_tests,
    snapshot,
)
from api.services.realtime_observability.slo import TARGETS_MS, evaluate_slos
from api.services.realtime_observability.tracing import get_trace_context, trace_session
from api.services.voice_runtime_cache import _assert_safe_payload, _key


def test_percentile_p50_p95_p99():
    reset_for_tests()
    for v in range(1, 101):
        record_stage_ms("stt", float(v))
    stats = snapshot()["stt"]
    assert stats["count"] == 100
    assert stats["p50"] == 50
    assert stats["p95"] == 95
    assert stats["p99"] == 99


def test_slo_document_has_pipeline_stages():
    for stage in (
        "stt",
        "normalize",
        "intent",
        "workflow",
        "llm_first_token",
        "tool_call",
        "tts_first_byte",
        "first_response",
        "turn_e2e",
        "call_startup",
        "websocket_connect",
    ):
        assert stage in TARGETS_MS
    report = evaluate_slos()
    assert "engineering" in report["note"].lower()
    assert "sla" in report["note"].lower()


def test_call_correlation_context():
    corr = CallCorrelation(
        call_id="abc",
        session_id="sess",
        organization_id=9,
        workflow_run_id=3,
        trace_id="abc",
    )
    with bind_call_correlation(corr), trace_session("sess", trace_id="abc"):
        assert get_call_id() == "abc"
        ctx = get_trace_context()
        assert ctx["call_id"] == "abc"
        assert ctx["trace_id"] == "abc"
        assert "X-Call-Id" in corr.as_headers()


def test_tenant_cache_key_requires_org_and_is_scoped():
    with pytest.raises(ValueError):
        _key(0, "workflow", "1")
    a = _key(11, "workflow", "wf-1")
    b = _key(22, "workflow", "wf-1")
    assert a != b
    assert a.startswith("voice_rt:11:")


def test_tenant_cache_rejects_sensitive_fields():
    with pytest.raises(ValueError):
        _assert_safe_payload({"phone": "+254700000000"})
    _assert_safe_payload({"node_count": 4, "name": "collections"})


def test_ws_handshake_records_connect_percentile():
    reset_for_tests()
    from api.services.realtime_observability.collector import VoiceObservabilityCollector

    VoiceObservabilityCollector.record_ws_handshake(42.0)
    stats = snapshot()["websocket_connect"]
    assert stats["count"] == 1
    assert stats["p50"] == 42.0
