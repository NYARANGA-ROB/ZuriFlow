"""OpenAI Whisper API fallback client (batch on buffered PCM)."""

from __future__ import annotations

import asyncio
import io
import time
import wave
from collections.abc import AsyncIterator

import httpx
from loguru import logger

from api.services.streaming_stt.config import StreamingSTTConfig
from api.services.streaming_stt.errors import WhisperFallbackError
from api.services.streaming_stt.types import (
    StreamingTranscriptEvent,
    StreamingTranscriptKind,
)


class WhisperFallbackClient:
    """Buffers PCM and transcribes via OpenAI ``/audio/transcriptions`` (Whisper)."""

    def __init__(
        self,
        *,
        api_key: str,
        config: StreamingSTTConfig,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._config = config
        self._base_url = (base_url or config.whisper_base_url).rstrip("/")
        self._buffer = bytearray()
        self._sample_rate = config.sample_rate
        self._connected = False
        self._event_queue: asyncio.Queue[StreamingTranscriptEvent | None] = asyncio.Queue(
            maxsize=config.transcript_queue_maxsize
        )
        self._flush_task: asyncio.Task | None = None
        self._last_flush_at = time.monotonic()

    @property
    def name(self) -> str:
        return "whisper"

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True
        self._buffer.clear()
        self._flush_task = asyncio.create_task(
            self._periodic_flush_loop(), name="whisper-flush"
        )
        logger.info("WhisperFallbackClient active")

    async def close(self) -> None:
        self._connected = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            await asyncio.gather(self._flush_task, return_exceptions=True)
        await self._event_queue.put(None)

    async def send_audio(self, pcm: bytes, *, sample_rate: int) -> None:
        if not self._connected:
            return
        self._sample_rate = sample_rate
        self._buffer.extend(pcm)
        max_bytes = int(
            self._config.whisper_max_buffer_ms
            / 1000
            * self._sample_rate
            * 2
        )
        if len(self._buffer) >= max_bytes:
            await self.flush_buffer()

    async def finalize_utterance(self) -> None:
        await self.flush_buffer()

    async def clear_buffer(self) -> None:
        self._buffer.clear()

    async def flush_buffer(self) -> StreamingTranscriptEvent | None:
        min_bytes = int(
            self._config.whisper_min_buffer_ms
            / 1000
            * self._sample_rate
            * 2
        )
        if len(self._buffer) < min_bytes:
            return None

        pcm = bytes(self._buffer)
        self._buffer.clear()
        self._last_flush_at = time.monotonic()

        try:
            text = await self._transcribe_pcm(pcm, self._sample_rate)
        except Exception as e:
            await self._event_queue.put(
                StreamingTranscriptEvent(
                    text=str(e),
                    kind=StreamingTranscriptKind.ERROR,
                    provider=self.name,
                )
            )
            raise WhisperFallbackError(str(e)) from e

        if not text.strip():
            return None

        event = StreamingTranscriptEvent(
            text=text.strip(),
            kind=StreamingTranscriptKind.FINAL,
            is_final=True,
            provider=self.name,
        )
        await self._event_queue.put(event)
        return event

    async def events(self) -> AsyncIterator[StreamingTranscriptEvent]:
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event

    async def _periodic_flush_loop(self) -> None:
        interval = max(self._config.whisper_min_buffer_ms / 1000.0, 0.5)
        while self._connected:
            await asyncio.sleep(interval)
            if len(self._buffer) > 0 and (time.monotonic() - self._last_flush_at) >= interval:
                try:
                    await self.flush_buffer()
                except WhisperFallbackError:
                    pass

    async def _transcribe_pcm(self, pcm: bytes, sample_rate: int) -> str:
        wav_bytes = _pcm_to_wav(pcm, sample_rate)
        url = f"{self._base_url}/audio/transcriptions"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                data={
                    "model": self._config.whisper_model,
                    "response_format": "json",
                },
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            )
        if response.status_code >= 400:
            raise WhisperFallbackError(
                f"Whisper API {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        return str(payload.get("text", ""))


def _pcm_to_wav(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
