"""Streaming STT errors."""

from __future__ import annotations


class StreamingSTTError(Exception):
    def __init__(self, message: str, *, code: str = "stt_error") -> None:
        super().__init__(message)
        self.code = code


class DeepgramConnectionError(StreamingSTTError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="deepgram_connection_error")


class WhisperFallbackError(StreamingSTTError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="whisper_fallback_error")


class STTTimeoutError(StreamingSTTError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="stt_timeout")
