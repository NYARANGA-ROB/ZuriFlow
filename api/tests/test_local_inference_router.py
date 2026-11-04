"""Tests for on-prem local inference routing."""

from __future__ import annotations

import json

import pytest

from api.services.local_inference.router import InferenceService, LocalInferenceRouter


def test_router_resolves_llm_endpoint():
    routes = {
        "llm": {
            "url": "http://dograh-vllm.dograh-inference.svc:8000/v1",
            "provider": "speaches",
            "default_model": "llama3",
        }
    }
    router = LocalInferenceRouter(routes)
    ep = router.get(InferenceService.LLM)
    assert ep is not None
    assert ep.url.endswith("/v1")
    assert ep.provider == "speaches"


def test_router_provider_defaults():
    routes = {
        "stt": {
            "url": "http://whisper:9000",
            "provider": "speaches",
            "default_model": "large-v3",
        }
    }
    router = LocalInferenceRouter(routes)
    defaults = router.as_provider_defaults()
    assert defaults["stt"]["base_url"] == "http://whisper:9000"


def test_router_summary_shape():
    router = LocalInferenceRouter({})
    summary = router.summary()
    assert summary["enabled"] is False
    assert "llm" in summary["endpoints"]


def test_load_routes_from_json(monkeypatch):
    payload = json.dumps(
        {"tts": {"url": "http://tts:5000", "provider": "speaches", "default_model": "piper"}}
    )
    monkeypatch.setattr("api.services.local_inference.router.LOCAL_INFERENCE_ROUTES_JSON", payload)
    monkeypatch.setattr("api.services.local_inference.router.LOCAL_INFERENCE_ENABLED", True)
    from api.services.local_inference.router import get_local_inference_router

    get_local_inference_router.cache_clear()
    router = get_local_inference_router()
    assert router.get(InferenceService.TTS) is not None
    get_local_inference_router.cache_clear()
