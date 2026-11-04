"""Interruption and synthesis cancellation tokens."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class SynthesisCancellationToken:
    """Cooperative cancellation for one TTS utterance."""

    generation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait_cancelled(self) -> None:
        await self._event.wait()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            from api.services.streaming_tts.errors import SynthesisCancelledError

            raise SynthesisCancelledError(self.generation_id)


@dataclass
class CancellationRegistry:
    """Tracks active synthesis generations for targeted interruption."""

    _active: dict[str, SynthesisCancellationToken] = field(default_factory=dict)

    def create(self, generation_id: str | None = None) -> SynthesisCancellationToken:
        token = SynthesisCancellationToken(
            generation_id=generation_id or uuid.uuid4().hex
        )
        self._active[token.generation_id] = token
        return token

    def get(self, generation_id: str) -> SynthesisCancellationToken | None:
        return self._active.get(generation_id)

    def cancel(self, generation_id: str | None = None) -> list[str]:
        """Cancel one generation or all active. Returns cancelled ids."""
        if generation_id is None:
            ids = list(self._active.keys())
            for token in self._active.values():
                token.cancel()
            return ids
        token = self._active.get(generation_id)
        if token:
            token.cancel()
            return [generation_id]
        return []

    def release(self, generation_id: str) -> None:
        self._active.pop(generation_id, None)

    def clear(self) -> None:
        self.cancel()
        self._active.clear()
