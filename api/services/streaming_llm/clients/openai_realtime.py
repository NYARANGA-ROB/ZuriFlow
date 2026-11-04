"""OpenAI Realtime API WebSocket client (text streaming)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlencode

import aiohttp
from loguru import logger

from api.services.streaming_llm.cancellation import GenerationCancellationRegistry
from api.services.streaming_llm.config import StreamingLLMConfig
from api.services.streaming_llm.errors import RealtimeConnectionError
from api.services.streaming_llm.types import ConversationMessage, ResponseStreamEvent, ResponseStreamKind


class OpenAIRealtimeClient:
    """Streams text from the OpenAI Realtime API over WebSocket."""

    def __init__(
        self,
        *,
        api_key: str,
        config: StreamingLLMConfig,
        session: aiohttp.ClientSession | None = None,
        cancellations: GenerationCancellationRegistry | None = None,
    ) -> None:
        self._api_key = api_key
        self._config = config
        self._session = session
        self._owns_session = session is None
        self._cancellations = cancellations or GenerationCancellationRegistry()
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False
        self._event_queue: asyncio.Queue[ResponseStreamEvent | None] = asyncio.Queue(
            maxsize=config.event_queue_maxsize
        )
        self._receiver_task: asyncio.Task | None = None
        self._generation_map: dict[str, str] = {}  # response_id -> generation_id

    @property
    def name(self) -> str:
        return "openai_realtime"

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None and not self._ws.closed

    def _build_url(self) -> str:
        params = urlencode({"model": self._config.model})
        return f"{self._config.base_url}?{params}"

    async def connect(self) -> None:
        if self.connected:
            return
        await self._open_connection()

    async def _open_connection(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        try:
            self._ws = await asyncio.wait_for(
                self._session.ws_connect(self._build_url(), headers=headers, heartbeat=None),
                timeout=self._config.connect_timeout_s,
            )
        except Exception as e:
            raise RealtimeConnectionError(f"failed to connect: {e}") from e

        self._connected = True
        if self._receiver_task is None or self._receiver_task.done():
            self._receiver_task = asyncio.create_task(
                self._receive_loop(), name="openai-realtime-receiver"
            )
        await self.update_session(instructions="")
        logger.debug("OpenAIRealtimeClient connected model={}", self._config.model)

    async def _ensure_connected(self) -> None:
        if self.connected:
            return
        last_error: Exception | None = None
        for attempt in range(self._config.max_reconnect_attempts):
            try:
                await self._open_connection()
                return
            except Exception as e:
                last_error = e
                await asyncio.sleep(self._config.reconnect_backoff_s * (2**attempt))
        raise RealtimeConnectionError(
            f"reconnect exhausted: {last_error}"
        ) from last_error

    async def close(self) -> None:
        self._connected = False
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
            await asyncio.gather(self._receiver_task, return_exceptions=True)
        if self._ws is not None and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
        self._cancellations.clear()
        await self._event_queue.put(None)

    async def update_session(
        self,
        *,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        await self._ensure_connected()
        session: dict[str, Any] = {
            "modalities": list(self._config.output_modalities),
            "instructions": instructions or "",
            "temperature": self._config.temperature,
        }
        token_cap = (
            max_output_tokens
            if max_output_tokens is not None
            else self._config.max_output_tokens
        )
        if token_cap is not None:
            session["max_response_output_tokens"] = token_cap
        if tools:
            session["tools"] = tools
        await self._send({"type": "session.update", "session": session})

    async def append_message(self, message: ConversationMessage) -> None:
        await self._ensure_connected()
        content_type = "input_text" if message.role == "user" else "output_text"
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": message.role,
                    "content": [{"type": content_type, "text": message.content}],
                },
            }
        )

    async def create_response(self, generation_id: str) -> None:
        await self._ensure_connected()
        self._cancellations.create(generation_id)
        await self._event_queue.put(
            ResponseStreamEvent(
                kind=ResponseStreamKind.GENERATION_START,
                generation_id=generation_id,
            )
        )
        await self._send({"type": "response.create"})

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        if not self.connected:
            return
        payload: dict[str, Any] = {"type": "response.cancel"}
        rid = response_id or self._cancellations.current_response_id()
        if rid:
            payload["response_id"] = rid
        await self._send(payload)

    async def events(self):
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event

    async def _send(self, payload: dict[str, Any]) -> None:
        await self._ensure_connected()
        if self._ws is None or self._ws.closed:
            raise RealtimeConnectionError("not connected")
        try:
            await self._ws.send_str(json.dumps(payload))
        except Exception as e:
            self._connected = False
            raise RealtimeConnectionError(f"send failed: {e}") from e

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if not self._connected:
                    break
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                data = json.loads(msg.data)
                for event in self._parse_server_event(data):
                    await self._event_queue.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("OpenAI Realtime receive loop ended: {}", e)
            await self._event_queue.put(
                ResponseStreamEvent(
                    kind=ResponseStreamKind.ERROR,
                    generation_id="",
                    text=str(e),
                )
            )
        finally:
            self._connected = False
            if self._ws is not None and not self._ws.closed:
                try:
                    await self._ws.close()
                except Exception:
                    pass
            self._ws = None

    def _parse_server_event(self, data: dict[str, Any]) -> list[ResponseStreamEvent]:
        event_type = data.get("type", "")
        response = data.get("response") or {}
        response_id = data.get("response_id") or response.get("id")

        if event_type == "response.created":
            gid = self._resolve_generation_id(response_id)
            if response_id and gid:
                self._cancellations.set_response_id(gid, response_id)
                self._generation_map[response_id] = gid
            return [
                ResponseStreamEvent(
                    kind=ResponseStreamKind.GENERATION_START,
                    generation_id=gid or "",
                    response_id=response_id,
                )
            ]

        if event_type in ("response.output_text.delta", "response.text.delta"):
            gid = self._resolve_generation_id(response_id)
            delta = data.get("delta", "")
            return [
                ResponseStreamEvent(
                    kind=ResponseStreamKind.TOKEN_DELTA,
                    generation_id=gid or "",
                    delta=delta,
                    text=delta,
                    response_id=response_id,
                )
            ]

        if event_type in ("response.output_text.done", "response.text.done"):
            gid = self._resolve_generation_id(response_id)
            text = data.get("text", "")
            return [
                ResponseStreamEvent(
                    kind=ResponseStreamKind.GENERATION_END,
                    generation_id=gid or "",
                    text=text,
                    is_final=True,
                    response_id=response_id,
                )
            ]

        if event_type in ("response.done", "response.completed"):
            gid = self._resolve_generation_id(response_id)
            if response_id:
                self._generation_map.pop(response_id, None)
            return [
                ResponseStreamEvent(
                    kind=ResponseStreamKind.GENERATION_END,
                    generation_id=gid or "",
                    is_final=True,
                    response_id=response_id,
                    metadata={"usage": response.get("usage")},
                )
            ]

        if event_type in ("response.cancelled", "response.canceled"):
            gid = self._resolve_generation_id(response_id)
            return [
                ResponseStreamEvent(
                    kind=ResponseStreamKind.CANCELLED,
                    generation_id=gid or "",
                    response_id=response_id,
                )
            ]

        if event_type == "error":
            return [
                ResponseStreamEvent(
                    kind=ResponseStreamKind.ERROR,
                    generation_id="",
                    text=json.dumps(data.get("error", data)),
                    metadata=data,
                )
            ]

        return []

    def _resolve_generation_id(self, response_id: str | None) -> str:
        if response_id and response_id in self._generation_map:
            return self._generation_map[response_id]
        gid = self._cancellations.find_generation_by_response_id(response_id)
        if gid:
            return gid
        return self._cancellations.latest_generation_id()
