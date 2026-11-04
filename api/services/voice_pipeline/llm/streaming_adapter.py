"""Bridge streaming LLM engine to voice_pipeline LLMService protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from api.services.streaming_llm.engine import StreamingLLMResponseEngine
from api.services.streaming_llm.types import ResponseStreamKind
from api.services.voice_pipeline.types import LLMMessage, LLMStreamEvent, LLMStreamKind


class StreamingLLMBridge:
    """Adapts ``StreamingLLMResponseEngine`` to ``LLMService``."""

    def __init__(self, engine: StreamingLLMResponseEngine) -> None:
        self._engine = engine

    async def start(self) -> None:
        await self._engine.start()

    async def stop(self) -> None:
        await self._engine.stop()

    async def set_system_prompt(self, prompt: str) -> None:
        await self._engine.set_system_prompt(prompt)

    async def interrupt(self) -> None:
        await self._engine.interrupt()

    async def apply_turn_budget(self, max_output_tokens: int) -> None:
        await self._engine.apply_turn_budget(max_output_tokens)

    async def generate(
        self, messages: list[LLMMessage], *, tools: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[LLMStreamEvent]:
        if tools:
            await self._engine.set_tools(tools)

        user_msgs = [m for m in messages if m.role == "user"]
        if user_msgs:
            await self._engine.ensure_user_turn(user_msgs[-1].content)
        await self._engine.generate_response()

        full_text: list[str] = []
        async for event in self._engine.stream():
            if event.kind == ResponseStreamKind.TOKEN_DELTA:
                full_text.append(event.delta)
                yield LLMStreamEvent(
                    kind=LLMStreamKind.TEXT_DELTA,
                    text=event.delta,
                )
            elif event.kind == ResponseStreamKind.SENTENCE_PARTIAL:
                yield LLMStreamEvent(
                    kind=LLMStreamKind.TEXT_DELTA,
                    text=event.delta or event.text,
                )
            elif event.kind == ResponseStreamKind.GENERATION_END:
                text = event.text or "".join(full_text)
                yield LLMStreamEvent(kind=LLMStreamKind.TEXT_DONE, text=text)
                break
            elif event.kind == ResponseStreamKind.CANCELLED:
                await self._engine.discard_pending_stream_events()
                break
            elif event.kind == ResponseStreamKind.ERROR:
                await self._engine.discard_pending_stream_events()
                break
