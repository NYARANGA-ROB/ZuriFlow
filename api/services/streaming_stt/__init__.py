from api.services.streaming_stt.config import DEFAULT_STREAMING_STT_CONFIG, StreamingSTTConfig

__all__ = [
    "DEFAULT_STREAMING_STT_CONFIG",
    "DeepgramStreamingClient",
    "PartialTranscriptHandler",
    "RealtimeTranscriptionService",
    "StreamingSTTClient",
    "StreamingSTTFallbackClient",
    "StreamingSTTConfig",
    "StreamingTranscriptEvent",
    "StreamingTranscriptKind",
    "STTProviderStatus",
    "TimeoutRecoveryManager",
    "WhisperFallbackClient",
    "create_realtime_transcription_service",
    "create_streaming_stt_bridge",
]


def __getattr__(name: str):
    if name == "DeepgramStreamingClient":
        from api.services.streaming_stt.clients.deepgram import DeepgramStreamingClient

        return DeepgramStreamingClient
    if name == "WhisperFallbackClient":
        from api.services.streaming_stt.clients.whisper import WhisperFallbackClient

        return WhisperFallbackClient
    if name in ("StreamingSTTClient", "StreamingSTTFallbackClient"):
        from api.services.streaming_stt import interfaces

        return getattr(interfaces, name)
    if name == "PartialTranscriptHandler":
        from api.services.streaming_stt.partials import PartialTranscriptHandler

        return PartialTranscriptHandler
    if name in ("create_realtime_transcription_service", "create_streaming_stt_bridge"):
        from api.services.streaming_stt import factory

        return getattr(factory, name)
    if name == "RealtimeTranscriptionService":
        from api.services.streaming_stt.realtime_service import RealtimeTranscriptionService

        return RealtimeTranscriptionService
    if name == "TimeoutRecoveryManager":
        from api.services.streaming_stt.recovery import TimeoutRecoveryManager

        return TimeoutRecoveryManager
    if name in ("StreamingTranscriptEvent", "StreamingTranscriptKind", "STTProviderStatus"):
        from api.services.streaming_stt import types

        return getattr(types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
