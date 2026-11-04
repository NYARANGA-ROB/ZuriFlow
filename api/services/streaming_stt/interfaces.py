"""STT client abstraction for realtime streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from api.services.streaming_stt.types import StreamingTranscriptEvent


class StreamingSTTClient(Protocol):
    """Low-latency streaming speech-to-text backend."""

    @property
    def name(self) -> str: ...

    @property
    def connected(self) -> bool: ...

    async def connect(self) -> None:
        """Open upstream connection / prepare client."""

    async def close(self) -> None:
        """Release upstream resources."""

    async def send_audio(self, pcm: bytes, *, sample_rate: int) -> None:
        """Stream a PCM chunk to the provider."""

    async def finalize_utterance(self) -> None:
        """Signal end of current utterance (provider-specific)."""

    async def clear_buffer(self) -> None:
        """Clear in-flight audio — used on user interruption."""

    def events(self) -> AsyncIterator[StreamingTranscriptEvent]: ...


class StreamingSTTFallbackClient(StreamingSTTClient, Protocol):
    """Batch-style fallback that accumulates audio before transcribing."""

    async def flush_buffer(self) -> StreamingTranscriptEvent | None: ...
