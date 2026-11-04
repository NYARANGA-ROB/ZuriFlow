from api.services.streaming_tts.config import DEFAULT_STREAMING_TTS_CONFIG, StreamingTTSConfig

__all__ = [
    "AudioBufferService",
    "CancellationRegistry",
    "DEFAULT_STREAMING_TTS_CONFIG",
    "ElevenLabsStreamingClient",
    "RealtimeStreamingTTSService",
    "StreamingPlaybackHandler",
    "StreamingTTSClient",
    "StreamingTTSConfig",
    "SynthesisCancellationToken",
    "TTSStreamEvent",
    "TTSStreamKind",
    "TextFragment",
    "create_realtime_streaming_tts",
    "create_streaming_tts_bridge",
]


def __getattr__(name: str):
    if name == "AudioBufferService":
        from api.services.streaming_tts.buffering import AudioBufferService

        return AudioBufferService
    if name in ("CancellationRegistry", "SynthesisCancellationToken"):
        from api.services.streaming_tts.cancellation import (
            CancellationRegistry,
            SynthesisCancellationToken,
        )

        return locals()[name]
    if name == "ElevenLabsStreamingClient":
        from api.services.streaming_tts.clients.elevenlabs import ElevenLabsStreamingClient

        return ElevenLabsStreamingClient
    if name in ("create_realtime_streaming_tts", "create_streaming_tts_bridge"):
        from api.services.streaming_tts import factory

        return getattr(factory, name)
    if name == "StreamingTTSClient":
        from api.services.streaming_tts.interfaces import StreamingTTSClient

        return StreamingTTSClient
    if name == "StreamingPlaybackHandler":
        from api.services.streaming_tts.playback import StreamingPlaybackHandler

        return StreamingPlaybackHandler
    if name == "RealtimeStreamingTTSService":
        from api.services.streaming_tts.realtime_service import RealtimeStreamingTTSService

        return RealtimeStreamingTTSService
    if name in ("TextFragment", "TTSStreamEvent", "TTSStreamKind"):
        from api.services.streaming_tts import types

        return getattr(types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
