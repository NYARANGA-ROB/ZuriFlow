"""Streaming TTS client abstraction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from api.services.streaming_tts.types import TextFragment, TTSStreamEvent


class StreamingTTSClient(Protocol):
    """Low-latency streaming text-to-speech backend."""

    @property
    def name(self) -> str: ...

    @property
    def connected(self) -> bool: ...

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def begin_utterance(self, generation_id: str) -> None:
        """Start a new synthesis generation (supports interruption per generation)."""

    async def push_text(self, fragment: TextFragment) -> None:
        """Stream incremental text for partial-response playback."""

    async def end_utterance(self, generation_id: str) -> None:
        """Signal end of text for the current utterance."""

    async def cancel(self, generation_id: str | None = None) -> None:
        """Cancel in-flight synthesis (interruption / barge-in)."""

    def events(self) -> AsyncIterator[TTSStreamEvent]: ...
