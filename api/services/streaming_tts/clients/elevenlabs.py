"""ElevenLabs WebSocket stream-input TTS client."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlencode

import aiohttp
from loguru import logger

from api.services.streaming_tts.cancellation import CancellationRegistry
from api.services.streaming_tts.config import StreamingTTSConfig
from api.services.streaming_tts.errors import ElevenLabsConnectionError, SynthesisCancelledError
from api.services.streaming_tts.types import TextFragment, TTSStreamEvent, TTSStreamKind


class ElevenLabsStreamingClient:
    """ElevenLabs ``/v1/text-to-speech/{voice_id}/stream-input`` WebSocket client."""

    def __init__(
        self,
        *,
        api_key: str,
        config: StreamingTTSConfig,
        session: aiohttp.ClientSession | None = None,
        cancellations: CancellationRegistry | None = None,
    ) -> None:
        self._api_key = api_key
        self._config = config
        self._session = session
        self._owns_session = session is None
        self._cancellations = cancellations or CancellationRegistry()
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False
        self._current_generation: str | None = None
        self._event_queue: asyncio.Queue[TTSStreamEvent | None] = asyncio.Queue(
            maxsize=config.audio_queue_maxsize
        )
        self._send_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=config.text_queue_maxsize
        )
        self._receiver_task: asyncio.Task | None = None
        self._sender_task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None and not self._ws.closed

    def _http_to_ws_base(self) -> str:
        return (
            self._config.elevenlabs_base_url.replace("https://", "wss://")
            .replace("http://", "ws://")
            .rstrip("/")
        )

    def _build_url(self) -> str:
        voice_id = self._config.elevenlabs_voice_id
        if not voice_id:
            raise ElevenLabsConnectionError("elevenlabs_voice_id is required")
        params = {
            "model_id": self._config.elevenlabs_model,
            "optimize_streaming_latency": str(self._config.elevenlabs_optimize_latency),
            "output_format": self._config.elevenlabs_output_format,
        }
        query = urlencode(params)
        return f"{self._http_to_ws_base()}/v1/text-to-speech/{voice_id}/stream-input?{query}"

    async def connect(self) -> None:
        if self.connected:
            return
        await self._open_connection()

    async def _open_connection(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

        url = self._build_url()
        try:
            self._ws = await asyncio.wait_for(
                self._session.ws_connect(
                    url,
                    headers={"xi-api-key": self._api_key},
                    heartbeat=None,
                ),
                timeout=self._config.connect_timeout_s,
            )
        except Exception as e:
            raise ElevenLabsConnectionError(f"failed to connect: {e}") from e

        # BOS — beginning of stream
        await self._ws.send_str(
            json.dumps(
                {
                    "text": " ",
                    "voice_settings": {
                        "stability": self._config.elevenlabs_stability,
                        "similarity_boost": self._config.elevenlabs_similarity_boost,
                        "speed": self._config.elevenlabs_speed,
                    },
                    "generation_config": {
                        "chunk_length_schedule": [50, 120, 160, 290],
                    },
                }
            )
        )

        self._connected = True
        if self._receiver_task is None or self._receiver_task.done():
            self._receiver_task = asyncio.create_task(
                self._receive_loop(), name="elevenlabs-tts-receiver"
            )
        if self._sender_task is None or self._sender_task.done():
            self._sender_task = asyncio.create_task(
                self._send_loop(), name="elevenlabs-tts-sender"
            )
        logger.debug("ElevenLabsStreamingClient connected")

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
        raise ElevenLabsConnectionError(f"reconnect exhausted: {last_error}") from last_error

    async def close(self) -> None:
        self._connected = False
        await self._send_queue.put(None)
        for task in (self._sender_task, self._receiver_task):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(
            *(t for t in (self._sender_task, self._receiver_task) if t),
            return_exceptions=True,
        )
        if self._ws is not None and not self._ws.closed:
            try:
                await self._ws.send_str(json.dumps({"text": ""}))
            except Exception:
                pass
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

    async def begin_utterance(self, generation_id: str) -> None:
        self._cancellations.create(generation_id)
        self._current_generation = generation_id
        await self._event_queue.put(
            TTSStreamEvent(
                kind=TTSStreamKind.SYNTHESIS_START,
                generation_id=generation_id,
            )
        )

    async def push_text(self, fragment: TextFragment) -> None:
        token = self._cancellations.get(fragment.generation_id)
        if token and token.is_cancelled:
            raise SynthesisCancelledError(fragment.generation_id)
        if not fragment.text:
            return
        await self._send_queue.put(
            {
                "text": fragment.text,
                "generation_id": fragment.generation_id,
                "flush": fragment.is_final,
            }
        )

    async def end_utterance(self, generation_id: str) -> None:
        await self._send_queue.put(
            {"text": "", "generation_id": generation_id, "flush": True}
        )

    async def cancel(self, generation_id: str | None = None) -> None:
        cancelled = self._cancellations.cancel(generation_id)
        for gid in cancelled:
            await self._event_queue.put(
                TTSStreamEvent(kind=TTSStreamKind.CANCELLED, generation_id=gid)
            )
        if self.connected and generation_id is None:
            try:
                await self._ws.send_str(json.dumps({"text": ""}))
            except Exception:
                pass

    async def events(self):
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event

    async def _send_loop(self) -> None:
        while self._connected:
            item = await self._send_queue.get()
            if item is None:
                break
            gid = item.get("generation_id", "")
            token = self._cancellations.get(gid)
            if token and token.is_cancelled:
                continue
            if not self.connected:
                try:
                    await self._ensure_connected()
                except Exception as e:
                    await self._event_queue.put(
                        TTSStreamEvent(
                            kind=TTSStreamKind.ERROR,
                            generation_id=gid,
                            metadata={"error": str(e)},
                        )
                    )
                    break
            try:
                await self._ws.send_str(json.dumps({"text": item.get("text", "")}))
                if item.get("flush"):
                    await self._event_queue.put(
                        TTSStreamEvent(
                            kind=TTSStreamKind.SYNTHESIS_END,
                            generation_id=gid,
                            is_final=True,
                        )
                    )
                    self._cancellations.release(gid)
            except Exception as e:
                await self._event_queue.put(
                    TTSStreamEvent(
                        kind=TTSStreamKind.ERROR,
                        generation_id=gid,
                        metadata={"error": str(e)},
                    )
                )
                break

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if not self._connected:
                    break
                gid = self._current_generation or ""
                token = self._cancellations.get(gid) if gid else None
                if token and token.is_cancelled:
                    continue

                if msg.type == aiohttp.WSMsgType.BINARY:
                    if not msg.data:
                        continue
                    await self._event_queue.put(
                        TTSStreamEvent(
                            kind=TTSStreamKind.AUDIO_CHUNK,
                            generation_id=gid,
                            audio=bytes(msg.data),
                            sample_rate=self._config.sample_rate,
                        )
                    )
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("error"):
                        await self._event_queue.put(
                            TTSStreamEvent(
                                kind=TTSStreamKind.ERROR,
                                generation_id=gid,
                                metadata=data,
                            )
                        )
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("ElevenLabs receive loop ended: {}", e)
            await self._event_queue.put(
                TTSStreamEvent(
                    kind=TTSStreamKind.ERROR,
                    generation_id=self._current_generation or "",
                    metadata={"error": str(e)},
                )
            )
        finally:
            self._connected = False
