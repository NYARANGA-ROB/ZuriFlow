"""Deepgram realtime WebSocket streaming client."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp
from loguru import logger

from api.services.streaming_stt.config import StreamingSTTConfig
from api.services.streaming_stt.errors import DeepgramConnectionError
from api.services.streaming_stt.types import (
    StreamingTranscriptEvent,
    StreamingTranscriptKind,
)


class DeepgramStreamingClient:
    """Low-latency Deepgram ``/v1/listen`` WebSocket client."""

    WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(
        self,
        *,
        api_key: str,
        config: StreamingSTTConfig,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._api_key = api_key
        self._config = config
        self._session = session
        self._owns_session = session is None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False
        self._event_queue: asyncio.Queue[StreamingTranscriptEvent | None] = asyncio.Queue(
            maxsize=config.transcript_queue_maxsize
        )
        self._receiver_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "deepgram"

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None and not self._ws.closed

    def _build_url(self) -> str:
        params = {
            "model": self._config.deepgram_model,
            "language": self._config.deepgram_language,
            "encoding": self._config.encoding,
            "sample_rate": str(self._config.sample_rate),
            "channels": str(self._config.channels),
            "interim_results": str(self._config.deepgram_interim_results).lower(),
            "endpointing": str(self._config.deepgram_endpointing_ms),
            "utterance_end_ms": str(self._config.deepgram_utterance_end_ms),
            "punctuate": "true",
            "smart_format": "true",
            "vad_events": "true",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        for term in self._config.deepgram_keyterms:
            query += f"&keyterm={term}"
        return f"{self.WS_URL}?{query}"

    async def connect(self) -> None:
        if self.connected:
            return
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

        url = self._build_url()
        try:
            self._ws = await asyncio.wait_for(
                self._session.ws_connect(
                    url,
                    headers={"Authorization": f"Token {self._api_key}"},
                    heartbeat=None,
                ),
                timeout=self._config.deepgram_connect_timeout_s,
            )
        except Exception as e:
            raise DeepgramConnectionError(f"failed to connect: {e}") from e

        self._connected = True
        self._receiver_task = asyncio.create_task(
            self._receive_loop(), name="deepgram-stt-receiver"
        )
        self._keepalive_task = asyncio.create_task(
            self._keepalive_loop(), name="deepgram-stt-keepalive"
        )
        logger.debug("DeepgramStreamingClient connected")

    async def close(self) -> None:
        self._connected = False
        for task in (self._keepalive_task, self._receiver_task):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(
            *(t for t in (self._keepalive_task, self._receiver_task) if t),
            return_exceptions=True,
        )
        if self._ws is not None and not self._ws.closed:
            try:
                await self._ws.send_str(json.dumps({"type": "CloseStream"}))
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
        await self._event_queue.put(None)

    async def send_audio(self, pcm: bytes, *, sample_rate: int) -> None:
        if not self.connected:
            raise DeepgramConnectionError("not connected")
        if sample_rate != self._config.sample_rate:
            logger.debug(
                "deepgram sample_rate mismatch got={} expected={}",
                sample_rate,
                self._config.sample_rate,
            )
        await self._ws.send_bytes(pcm)

    async def finalize_utterance(self) -> None:
        if self.connected:
            await self._ws.send_str(json.dumps({"type": "Finalize"}))

    async def clear_buffer(self) -> None:
        if self.connected:
            await self._ws.send_str(json.dumps({"type": "Finalize"}))

    async def events(self):
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event

    async def _keepalive_loop(self) -> None:
        while self._connected:
            await asyncio.sleep(5.0)
            if not self.connected:
                break
            try:
                await self._ws.send_str(json.dumps({"type": "KeepAlive"}))
            except Exception:
                break

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if not self._connected:
                    break
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    for event in self._parse_message(data):
                        await self._event_queue.put(event)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Deepgram receive loop ended: {}", e)
            await self._event_queue.put(
                StreamingTranscriptEvent(
                    text=str(e),
                    kind=StreamingTranscriptKind.ERROR,
                    provider=self.name,
                )
            )
        finally:
            self._connected = False

    def _parse_message(self, data: dict[str, Any]) -> list[StreamingTranscriptEvent]:
        msg_type = data.get("type")
        if msg_type == "SpeechStarted":
            return [
                StreamingTranscriptEvent(
                    text="",
                    kind=StreamingTranscriptKind.SPEECH_START,
                    provider=self.name,
                    start_ms=data.get("start") or data.get("timestamp"),
                )
            ]
        if msg_type == "UtteranceEnd":
            return [
                StreamingTranscriptEvent(
                    text="",
                    kind=StreamingTranscriptKind.SPEECH_END,
                    provider=self.name,
                )
            ]
        if msg_type == "Results":
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [])
            if not alternatives:
                return []
            alt = alternatives[0]
            transcript = (alt.get("transcript") or "").strip()
            if not transcript:
                return []
            confidence = alt.get("confidence")
            is_final = bool(data.get("is_final"))
            start = data.get("start")
            duration = data.get("duration")
            end = (start or 0) + (duration or 0) if start is not None else None
            kind = (
                StreamingTranscriptKind.FINAL
                if is_final
                else StreamingTranscriptKind.PARTIAL
            )
            return [
                StreamingTranscriptEvent(
                    text=transcript,
                    kind=kind,
                    is_final=is_final,
                    confidence=confidence,
                    provider=self.name,
                    start_ms=(start or 0) * 1000 if start is not None else None,
                    end_ms=end * 1000 if end is not None else None,
                    metadata={"speech_final": data.get("speech_final")},
                )
            ]
        if msg_type == "Error":
            return [
                StreamingTranscriptEvent(
                    text=json.dumps(data),
                    kind=StreamingTranscriptKind.ERROR,
                    provider=self.name,
                )
            ]
        return []
