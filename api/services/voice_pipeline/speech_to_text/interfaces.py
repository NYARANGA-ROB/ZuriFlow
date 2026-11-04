"""Speech-to-text service contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from api.services.voice_pipeline.types import AudioChunk, TranscriptEvent


class SpeechToTextService(Protocol):
    """Streaming STT: push audio, pull transcript events."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def push_audio(self, chunk: AudioChunk) -> None: ...

    def transcripts(self) -> AsyncIterator[TranscriptEvent]: ...
