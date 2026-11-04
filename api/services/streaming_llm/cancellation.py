"""Generation cancellation for interruption-aware LLM responses."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class GenerationCancellationToken:
    generation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    response_id: str | None = None
    _event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            from api.services.streaming_llm.errors import GenerationCancelledError

            raise GenerationCancelledError(self.generation_id)


@dataclass
class GenerationCancellationRegistry:
    _active: dict[str, GenerationCancellationToken] = field(default_factory=dict)
    _current_response_id: str | None = None

    def create(self, generation_id: str | None = None) -> GenerationCancellationToken:
        token = GenerationCancellationToken(
            generation_id=generation_id or uuid.uuid4().hex
        )
        self._active[token.generation_id] = token
        return token

    def get(self, generation_id: str) -> GenerationCancellationToken | None:
        return self._active.get(generation_id)

    def set_response_id(self, generation_id: str, response_id: str) -> None:
        token = self._active.get(generation_id)
        if token:
            token.response_id = response_id
        self._current_response_id = response_id

    def current_response_id(self) -> str | None:
        return self._current_response_id

    def cancel(self, generation_id: str | None = None) -> list[str]:
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

    def latest_generation_id(self) -> str:
        if not self._active:
            return ""
        return next(reversed(self._active.keys()))

    def find_generation_by_response_id(self, response_id: str | None) -> str:
        if not response_id:
            return ""
        for token in self._active.values():
            if token.response_id == response_id:
                return token.generation_id
        return ""

    def clear(self) -> None:
        self.cancel()
        self._active.clear()
        self._current_response_id = None
