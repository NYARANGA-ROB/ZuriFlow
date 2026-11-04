"""Tests for Kenya production optimizations."""

from __future__ import annotations

import time

from api.services.kenya_production.profile import (
    KENYA_PRODUCTION_LLM_CONFIG,
    KENYA_PRODUCTION_PIPELINE_CONFIG,
    resolve_pipeline_config,
)
from api.services.kenya_production.resilience import CircuitBreaker
from api.services.org_config_cache import OrgConfigCache
from api.services.realtime_voice_pipeline.config import LOW_LATENCY_PIPELINE_CONFIG


def test_org_config_cache_ttl():
    cache = OrgConfigCache[str](ttl_s=0.05)
    cache.set(1, "WHATSAPP_CONFIGURATION", "cfg-a")
    assert cache.get(1, "WHATSAPP_CONFIGURATION") == "cfg-a"
    time.sleep(0.06)
    assert cache.get(1, "WHATSAPP_CONFIGURATION") is None


def test_org_config_cache_invalidate():
    cache = OrgConfigCache[str]()
    cache.set(2, "MPESA_DARAJA_CONFIGURATION", "m")
    cache.invalidate(2)
    assert cache.get(2, "MPESA_DARAJA_CONFIGURATION") is None


def test_circuit_breaker_opens_and_recovers():
    breaker = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout_s=0.05)
    assert breaker.allow()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.allow()
    breaker.record_failure()
    assert not breaker.allow()
    time.sleep(0.06)
    assert breaker.allow()


def test_kenya_production_pipeline_tighter_queues(monkeypatch):
    monkeypatch.setattr(
        "api.services.kenya_production.profile.KENYA_PRODUCTION_MODE",
        True,
    )
    base = LOW_LATENCY_PIPELINE_CONFIG
    resolved = resolve_pipeline_config(base)
    assert resolved.inbound_audio_maxsize <= KENYA_PRODUCTION_PIPELINE_CONFIG.inbound_audio_maxsize
    assert resolved.target_e2e_latency_ms <= 700


def test_kenya_production_tts_preserves_voice_id(monkeypatch):
    from dataclasses import replace

    from api.services.kenya_production.profile import resolve_tts_config
    from api.services.realtime_voice_pipeline.low_latency_profiles import LOW_LATENCY_TTS_CONFIG

    monkeypatch.setattr(
        "api.services.kenya_production.profile.KENYA_PRODUCTION_MODE",
        True,
    )
    base = replace(LOW_LATENCY_TTS_CONFIG, elevenlabs_voice_id="voice-abc")
    resolved = resolve_tts_config(base)
    assert resolved is not None
    assert resolved.elevenlabs_voice_id == "voice-abc"


def test_kenya_production_llm_token_cap():
    assert KENYA_PRODUCTION_LLM_CONFIG.max_output_tokens <= 512
