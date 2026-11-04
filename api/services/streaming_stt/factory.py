"""Factory for realtime streaming STT services."""

from __future__ import annotations

from api.services.streaming_stt.config import StreamingSTTConfig, DEFAULT_STREAMING_STT_CONFIG
from api.services.streaming_stt.realtime_service import RealtimeTranscriptionService
from api.services.voice_pipeline.speech_to_text.streaming_adapter import StreamingSTTBridge


def create_realtime_transcription_service(
    *,
    deepgram_api_key: str,
    whisper_api_key: str,
    config: StreamingSTTConfig | None = None,
) -> RealtimeTranscriptionService:
    return RealtimeTranscriptionService(
        deepgram_api_key=deepgram_api_key,
        whisper_api_key=whisper_api_key,
        config=config or DEFAULT_STREAMING_STT_CONFIG,
    )


def create_streaming_stt_bridge(
    *,
    deepgram_api_key: str,
    whisper_api_key: str,
    config: StreamingSTTConfig | None = None,
) -> StreamingSTTBridge:
    service = create_realtime_transcription_service(
        deepgram_api_key=deepgram_api_key,
        whisper_api_key=whisper_api_key,
        config=config,
    )
    return StreamingSTTBridge(service)
