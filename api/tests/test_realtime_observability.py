"""Tests for realtime voice observability."""

import pytest

from api.services.realtime_observability.collector import VoiceObservabilityCollector
from api.services.realtime_observability.health import HEALTH_SERVICE
from api.services.realtime_observability.metrics import (
    E2E_LATENCY_MS,
    RECONNECTS_TOTAL,
    REGISTRY,
)
from api.services.realtime_observability.prometheus_registry import Counter, Histogram
from api.services.realtime_observability.tracing import trace_session, TRACING


def test_prometheus_histogram_export():
    h = Histogram("test_latency_ms", "test", buckets=(10, 100, 1000))
    h.observe(25.0)
    h.observe(150.0)
    lines = h.collect()
    text = "\n".join(lines)
    assert "test_latency_ms_bucket" in text
    assert "test_latency_ms_count" in text


def test_prometheus_registry_generate():
    c = Counter("test_counter_total", "test", registry=REGISTRY)
    c.inc()
    body = REGISTRY.generate_latest()
    assert "dograh_realtime" in body or "test_counter_total" in body


def test_voice_observability_collector_turn_stages():
    col = VoiceObservabilityCollector(workflow_run_id=1, session_id="sess-1")
    col.begin_turn()
    col.record_turn_stage("stt_final", value_ms=120.0)
    col.record_turn_stage("llm_first_token", value_ms=350.0)
    col.record_turn_complete(
        {
            "turn_e2e_ms": 600.0,
            "stt_to_llm_start_ms": 350.0,
            "tts_to_audio_ms": 200.0,
        }
    )


def test_interruption_and_reconnect_counters():
    VoiceObservabilityCollector.record_interruption(source="vad")
    RECONNECTS_TOTAL.inc(endpoint="realtime_audio")
    E2E_LATENCY_MS.observe(750.0)
    body = REGISTRY.generate_latest()
    assert "dograh_realtime_interruptions_total" in body
    assert "dograh_realtime_reconnects_total" in body


@pytest.mark.asyncio
async def test_health_liveness():
    status = HEALTH_SERVICE.liveness()
    assert status.status == "ok"


@pytest.mark.asyncio
async def test_health_readiness():
    status = await HEALTH_SERVICE.readiness()
    assert status.status in ("ok", "degraded")


def test_trace_session_context():
    spans: list = []
    TRACING.register_exporter(spans.append)
    with trace_session("abc123"):
        with TRACING.span("test.op", key="value"):
            pass
    assert spans
    assert spans[0]["name"] == "test.op"
