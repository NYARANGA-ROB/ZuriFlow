"""Streaming TTS errors."""

from __future__ import annotations


class StreamingTTSError(Exception):
    def __init__(self, message: str, *, code: str = "tts_error") -> None:
        super().__init__(message)
        self.code = code


class ElevenLabsConnectionError(StreamingTTSError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="elevenlabs_connection_error")


class SynthesisCancelledError(StreamingTTSError):
    def __init__(self, generation_id: str) -> None:
        super().__init__(
            f"synthesis cancelled: {generation_id}", code="synthesis_cancelled"
        )
        self.generation_id = generation_id


class PlaybackBufferError(StreamingTTSError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="playback_buffer_error")
