"""Tests for streaming STT partial handling and recovery."""

import asyncio

import pytest

from api.services.streaming_stt.config import StreamingSTTConfig
from api.services.streaming_stt.partials import PartialTranscriptHandler
from api.services.streaming_stt.recovery import TimeoutRecoveryManager
from api.services.streaming_stt.types import StreamingTranscriptKind


def test_partial_incremental_delta():
    handler = PartialTranscriptHandler(provider="deepgram")
    events = handler.on_partial("hello")
    assert any(e.kind == StreamingTranscriptKind.PARTIAL for e in events)
    assert any(e.kind == StreamingTranscriptKind.INCREMENTAL for e in events)

    events2 = handler.on_partial("hello world")
    incremental = [e for e in events2 if e.kind == StreamingTranscriptKind.INCREMENTAL]
    assert incremental[0].delta == " world"


def test_final_and_interrupt():
    handler = PartialTranscriptHandler(provider="deepgram")
    handler.on_partial("test")
    finals = handler.on_final("test phrase")
    assert finals[0].kind == StreamingTranscriptKind.FINAL
    assert finals[0].text == "test phrase"

    handler.on_partial("more")
    interrupted = handler.reset(interrupted=True)
    assert interrupted is not None
    assert interrupted.kind == StreamingTranscriptKind.INTERRUPTED


def test_recovery_reconnect_then_fallback():
    cfg = StreamingSTTConfig(deepgram_reconnect_attempts=2)
    mgr = TimeoutRecoveryManager(cfg)
    mgr.mark_disconnected()
    assert mgr.should_reconnect_deepgram() is True
    mgr.record_reconnect_attempt()
    mgr.record_reconnect_attempt()
    assert mgr.should_fallback_to_whisper() is True


@pytest.mark.asyncio
async def test_whisper_pcm_to_wav_transcription(monkeypatch):
    from api.services.streaming_stt.clients.whisper import WhisperFallbackClient

    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"text": "fallback transcript"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, data=None, files=None):
            captured["url"] = url
            captured["model"] = data.get("model")
            return FakeResponse()

    monkeypatch.setattr(
        "api.services.streaming_stt.clients.whisper.httpx.AsyncClient", FakeClient
    )

    client = WhisperFallbackClient(api_key="sk-test", config=StreamingSTTConfig())
    await client.connect()
    pcm = b"\x00\x00" * 8000
    await client.send_audio(pcm, sample_rate=16000)
    event = await client.flush_buffer()
    await client.close()

    assert event is not None
    assert event.text == "fallback transcript"
    assert captured["model"] == "whisper-1"
