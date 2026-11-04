"""Factory helpers for streaming TTS."""

from __future__ import annotations

from dataclasses import replace

from api.services.streaming_tts.config import StreamingTTSConfig, DEFAULT_STREAMING_TTS_CONFIG
from api.services.streaming_tts.realtime_service import RealtimeStreamingTTSService
from api.services.voice_pipeline.text_to_speech.streaming_adapter import StreamingTTSBridge


def create_realtime_streaming_tts(
    *,
    api_key: str,
    voice_id: str,
    config: StreamingTTSConfig | None = None,
    session_id: str | None = None,
) -> RealtimeStreamingTTSService:
    base = config or DEFAULT_STREAMING_TTS_CONFIG
    cfg = replace(base, elevenlabs_voice_id=voice_id)
    return RealtimeStreamingTTSService(
        api_key=api_key,
        config=cfg,
        session_id=session_id,
    )


def create_streaming_tts_bridge(
    *,
    api_key: str,
    voice_id: str,
    config: StreamingTTSConfig | None = None,
) -> StreamingTTSBridge:
    service = create_realtime_streaming_tts(
        api_key=api_key, voice_id=voice_id, config=config
    )
    return StreamingTTSBridge(service)
