"""Realtime streaming LLM response engine."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

from api.services.streaming_llm.cancellation import GenerationCancellationRegistry
from api.services.streaming_llm.clients.openai_realtime import OpenAIRealtimeClient
from api.services.streaming_llm.config import StreamingLLMConfig, DEFAULT_STREAMING_LLM_CONFIG
from api.services.streaming_llm.conversation import ConversationStateManager
from api.services.streaming_llm.tokens import TokenStreamingHandler
from api.services.streaming_llm.types import ResponseStreamEvent, ResponseStreamKind


class StreamingLLMResponseEngine:
    """Orchestrates OpenAI Realtime streaming with memory and interruption."""

    def __init__(
        self,
        *,
        api_key: str,
        config: StreamingLLMConfig = DEFAULT_STREAMING_LLM_CONFIG,
        client: OpenAIRealtimeClient | None = None,
    ) -> None:
        self._config = config
        self._cancellations = GenerationCancellationRegistry()
        self._conversation = ConversationStateManager(config)
        self._client = client or OpenAIRealtimeClient(
            api_key=api_key,
            config=config,
            cancellations=self._cancellations,
        )
        self._out_queue: asyncio.Queue[ResponseStreamEvent | None] = asyncio.Queue(
            maxsize=config.event_queue_maxsize
        )
        self._token_handlers: dict[str, TokenStreamingHandler] = {}
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._current_generation: str | None = None

    @property
    def conversation(self) -> ConversationStateManager:
        return self._conversation

    async def start(self) -> None:
        await self._client.connect()
        self._tasks = [
            asyncio.create_task(self._client_events_loop(), name="llm-client-events"),
        ]

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._client.close()
        await self._out_queue.put(None)

    async def set_system_prompt(self, prompt: str) -> None:
        self._conversation.set_system_prompt(prompt)
        await self._client.update_session(instructions=prompt)

    async def set_tools(self, tools: list[dict[str, Any]]) -> None:
        await self._client.update_session(
            instructions=self._conversation.system_prompt,
            tools=tools,
        )

    async def apply_turn_budget(self, max_output_tokens: int) -> None:
        await self._client.update_session(
            instructions=self._conversation.system_prompt,
            max_output_tokens=max_output_tokens,
        )

    async def send_user_message(self, text: str) -> str:
        """Append user turn to memory and return generation id."""
        await self.ensure_user_turn(text)
        return await self.generate_response()

    async def ensure_user_turn(self, text: str) -> None:
        """Append user message to realtime session only if not already the latest turn."""
        cleaned = text.strip()
        last = self._conversation.last_user_message()
        if last and last.content.strip() == cleaned:
            return
        msg = self._conversation.append_user(cleaned)
        await self._client.append_message(msg)

    async def generate_response(self, generation_id: str | None = None) -> str:
        gid = generation_id or uuid.uuid4().hex
        self._current_generation = gid
        self._token_handlers[gid] = TokenStreamingHandler(gid, self._config)
        self._cancellations.create(gid)
        await self._client.create_response(gid)
        return gid

    async def interrupt(self, generation_id: str | None = None) -> None:
        """Cancel in-flight generation (barge-in)."""
        gid = generation_id or self._current_generation
        cancelled = self._cancellations.cancel(gid)
        token = self._cancellations.get(gid) if gid else None
        await self._client.cancel_response(
            response_id=token.response_id if token else None
        )
        for cid in cancelled:
            handler = self._token_handlers.get(cid)
            if handler:
                for event in handler.reset(generation_id=cid):
                    await self._out_queue.put(event)
            self._token_handlers.pop(cid, None)
            self._cancellations.release(cid)
        if gid is None or self._current_generation == gid:
            self._current_generation = None
        await self.discard_pending_stream_events()

    async def discard_pending_stream_events(self) -> None:
        """Drop unconsumed events from a cancelled or errored generation."""
        preserved: list[ResponseStreamEvent | None] = []
        while True:
            try:
                event = self._out_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if event is None:
                preserved.append(event)
        for event in preserved:
            await self._out_queue.put(event)

    def stream(self) -> AsyncIterator[ResponseStreamEvent]:
        return self._iter_stream()

    async def _iter_stream(self) -> AsyncIterator[ResponseStreamEvent]:
        while True:
            event = await self._out_queue.get()
            if event is None:
                break
            yield event

    async def _client_events_loop(self) -> None:
        try:
            async for raw in self._client.events():
                if self._stop.is_set():
                    break
                await self._process_raw_event(raw)
        except asyncio.CancelledError:
            pass

    async def _process_raw_event(self, raw: ResponseStreamEvent) -> None:
        gid = raw.generation_id or self._current_generation or ""
        token = self._cancellations.get(gid) if gid else None
        if token and token.is_cancelled and raw.kind != ResponseStreamKind.CANCELLED:
            return

        if raw.response_id and gid:
            self._cancellations.set_response_id(gid, raw.response_id)

        handler = self._token_handlers.get(gid)
        if raw.kind == ResponseStreamKind.TOKEN_DELTA:
            if handler is None:
                handler = TokenStreamingHandler(gid, self._config)
                self._token_handlers[gid] = handler
            for event in handler.on_token_delta(raw.delta):
                await self._out_queue.put(event)
            return

        if raw.kind in (
            ResponseStreamKind.GENERATION_END,
            ResponseStreamKind.GENERATION_START,
            ResponseStreamKind.CANCELLED,
            ResponseStreamKind.ERROR,
        ):
            if handler and raw.kind == ResponseStreamKind.GENERATION_END:
                final_text = raw.text or handler._buffer
                for event in handler.on_generation_end(final_text):
                    await self._out_queue.put(event)
                if final_text.strip():
                    self._conversation.append_assistant(final_text.strip())
                self._token_handlers.pop(gid, None)
                self._cancellations.release(gid)
                if self._current_generation == gid:
                    self._current_generation = None
            await self._out_queue.put(raw)
            return

        await self._out_queue.put(raw)
