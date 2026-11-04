"""Text-to-speech service contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from api.services.voice_pipeline.types import AudioChunk, TTSRequest


class TextToSpeechService(Protocol):
    """Streaming TTS: push text, pull audio chunks."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def synthesize(self, request: TTSRequest) -> AsyncIterator[AudioChunk]: ...
