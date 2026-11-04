"""Bidirectional audio streaming contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from api.services.voice_pipeline.types import AudioChunk, VoicePipelineConfig


class AudioInbound(Protocol):
    """Source of caller audio."""

    def audio_chunks(self) -> AsyncIterator[AudioChunk]: ...


class AudioOutbound(Protocol):
    """Sink for synthesized / bot audio."""

    async def send(self, chunk: AudioChunk) -> None: ...


class MediaTransport(Protocol):
    """Wraps a carrier WebSocket (or WebRTC peer) as async audio streams."""

    async def open(self, config: VoicePipelineConfig, websocket: Any) -> None: ...

    async def close(self) -> None: ...

    def inbound(self) -> AudioInbound: ...

    def outbound(self) -> AudioOutbound: ...
