"""LLM service contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from api.services.voice_pipeline.types import LLMMessage, LLMStreamEvent


class LLMService(Protocol):
    """Text LLM with streaming token output."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def set_system_prompt(self, prompt: str) -> None: ...

    async def generate(
        self, messages: list[LLMMessage], *, tools: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMStreamEvent]: ...


class RealtimeLLMService(Protocol):
    """Speech-to-speech model that owns audio I/O."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def set_system_prompt(self, prompt: str) -> None: ...
