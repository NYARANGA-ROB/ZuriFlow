"""Streaming LLM client abstraction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from api.services.streaming_llm.types import ConversationMessage, ResponseStreamEvent


class StreamingLLMClient(Protocol):
    """Low-latency streaming LLM backend (OpenAI Realtime, etc.)."""

    @property
    def name(self) -> str: ...

    @property
    def connected(self) -> bool: ...

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def update_session(
        self,
        *,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> None: ...

    async def append_message(self, message: ConversationMessage) -> None: ...

    async def create_response(self, generation_id: str) -> None: ...

    async def cancel_response(self, *, response_id: str | None = None) -> None: ...

    def events(self) -> AsyncIterator[ResponseStreamEvent]: ...
