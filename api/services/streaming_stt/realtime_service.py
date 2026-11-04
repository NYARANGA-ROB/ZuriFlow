"""Realtime transcription orchestration service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from loguru import logger

from api.services.streaming_stt.clients.deepgram import DeepgramStreamingClient
from api.services.streaming_stt.clients.whisper import WhisperFallbackClient
from api.services.streaming_stt.config import StreamingSTTConfig, DEFAULT_STREAMING_STT_CONFIG
from api.services.streaming_stt.errors import DeepgramConnectionError, STTTimeoutError
from api.services.streaming_stt.partials import PartialTranscriptHandler
from api.services.streaming_stt.recovery import TimeoutRecoveryManager
from api.services.streaming_stt.types import (
    STTProviderStatus,
    StreamingTranscriptEvent,
    StreamingTranscriptKind,
)
from api.services.voice_pipeline.types import AudioChunk


class RealtimeTranscriptionService:
    """Async STT pipeline: Deepgram streaming with Whisper fallback and interruption."""

    def __init__(
        self,
        *,
        deepgram_api_key: str,
        whisper_api_key: str,
        config: StreamingSTTConfig = DEFAULT_STREAMING_STT_CONFIG,
        deepgram: DeepgramStreamingClient | None = None,
        whisper: WhisperFallbackClient | None = None,
    ) -> None:
        self._config = config
        self._deepgram = deepgram or DeepgramStreamingClient(
            api_key=deepgram_api_key, config=config
        )
        self._whisper = whisper or WhisperFallbackClient(
            api_key=whisper_api_key, config=config
        )
        self._recovery = TimeoutRecoveryManager(config)
        self._partials = PartialTranscriptHandler(provider="deepgram")

        self._audio_queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue(
            maxsize=config.audio_queue_maxsize
        )
        self._out_queue: asyncio.Queue[StreamingTranscriptEvent | None] = asyncio.Queue(
            maxsize=config.transcript_queue_maxsize
        )

        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._interrupt = asyncio.Event()

    async def start(self) -> None:
        await self._connect_primary()
        self._tasks = [
            asyncio.create_task(self._audio_pump(), name="stt-audio-pump"),
            asyncio.create_task(self._deepgram_events_loop(), name="stt-deepgram-events"),
            asyncio.create_task(self._whisper_events_loop(), name="stt-whisper-events"),
            asyncio.create_task(self._watchdog_loop(), name="stt-watchdog"),
        ]

    async def stop(self) -> None:
        self._stop.set()
        await self._audio_queue.put(None)
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._deepgram.close()
        await self._whisper.close()
        await self._out_queue.put(None)

    async def push_audio(self, chunk: AudioChunk) -> None:
        timeout = self._config.audio_put_timeout_s
        if timeout <= 0:
            try:
                self._audio_queue.put_nowait(chunk)
            except asyncio.QueueFull:
                try:
                    self._audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    self._audio_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    logger.warning("streaming_stt audio queue saturated — dropping chunk")
            return
        try:
            await asyncio.wait_for(self._audio_queue.put(chunk), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("streaming_stt audio queue saturated — dropping chunk")

    async def interrupt(self) -> None:
        """Barge-in: clear buffers and emit interrupted event."""
        self._interrupt.set()
        if self._config.interrupt_clear_buffer:
            await self._deepgram.clear_buffer()
            await self._whisper.clear_buffer()
        interrupted = self._partials.reset(interrupted=True)
        if interrupted:
            await self._out_queue.put(interrupted)
        self._interrupt.clear()

    async def transcripts(self) -> AsyncIterator[StreamingTranscriptEvent]:
        while True:
            event = await self._out_queue.get()
            if event is None:
                break
            yield event

    def status(self) -> STTProviderStatus:
        return STTProviderStatus(
            active_provider=(
                self._whisper.name
                if self._recovery.using_fallback
                else self._deepgram.name
            ),
            deepgram_connected=self._recovery.deepgram_connected,
            fallback_active=self._recovery.using_fallback,
            reconnect_attempts=self._recovery.reconnect_attempts,
            last_event_age_ms=self._recovery.last_event_age_ms(),
        )

    async def _connect_primary(self) -> None:
        try:
            await self._deepgram.connect()
            self._recovery.mark_connected()
            self._partials.provider = self._deepgram.name
        except DeepgramConnectionError as e:
            logger.warning("Deepgram connect failed, activating whisper fallback: {}", e)
            await self._activate_fallback(reason=str(e))

    async def _activate_fallback(self, *, reason: str) -> None:
        if self._recovery.using_fallback:
            return
        self._recovery.mark_fallback()
        self._partials.provider = self._whisper.name
        await self._deepgram.close()
        await self._whisper.connect()
        await self._out_queue.put(
            StreamingTranscriptEvent(
                text=reason,
                kind=StreamingTranscriptKind.PROVIDER_SWITCH,
                provider=self._whisper.name,
                metadata={"from": "deepgram", "to": "whisper"},
            )
        )

    async def _audio_pump(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = await self._audio_queue.get()
            except asyncio.CancelledError:
                break
            if chunk is None:
                break
            if self._interrupt.is_set():
                continue

            self._recovery.touch_audio()
            client = self._whisper if self._recovery.using_fallback else self._deepgram
            if not client.connected:
                continue
            try:
                await client.send_audio(chunk.pcm, sample_rate=chunk.sample_rate)
            except Exception as e:
                logger.warning("streaming_stt send_audio failed: {}", e)
                if not self._recovery.using_fallback:
                    await self._handle_deepgram_failure(str(e))

    async def _deepgram_events_loop(self) -> None:
        try:
            async for raw in self._deepgram.events():
                if self._recovery.using_fallback:
                    continue
                self._recovery.touch_event()
                for event in self._normalize_raw_event(raw):
                    await self._out_queue.put(event)
                if raw.kind == StreamingTranscriptKind.ERROR:
                    await self._handle_deepgram_failure(raw.text)
        except asyncio.CancelledError:
            pass

    async def _whisper_events_loop(self) -> None:
        try:
            async for raw in self._whisper.events():
                if not self._recovery.using_fallback:
                    continue
                self._recovery.touch_event()
                for event in self._normalize_raw_event(raw):
                    await self._out_queue.put(event)
        except asyncio.CancelledError:
            pass

    async def _watchdog_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self._config.watchdog_interval_s)
            if self._stop.is_set():
                break
            try:
                self._recovery.check_idle_timeout()
            except STTTimeoutError as e:
                logger.warning("{}", e)
                if not self._recovery.using_fallback:
                    await self._handle_deepgram_failure(str(e))

    async def _handle_deepgram_failure(self, reason: str) -> None:
        self._recovery.mark_disconnected()
        if self._recovery.should_reconnect_deepgram():
            self._recovery.record_reconnect_attempt()
            try:
                await self._deepgram.connect()
                self._recovery.mark_primary_restored()
                self._partials.provider = self._deepgram.name
                await self._whisper.close()
                await self._out_queue.put(
                    StreamingTranscriptEvent(
                        text="deepgram reconnected",
                        kind=StreamingTranscriptKind.PROVIDER_SWITCH,
                        provider=self._deepgram.name,
                        metadata={"restored": True},
                    )
                )
                return
            except DeepgramConnectionError:
                pass
        if self._recovery.should_fallback_to_whisper() or self._recovery.using_fallback:
            await self._activate_fallback(reason=reason)

    def _normalize_raw_event(
        self, raw: StreamingTranscriptEvent
    ) -> list[StreamingTranscriptEvent]:
        if raw.kind == StreamingTranscriptKind.ERROR:
            return [raw]
        if raw.kind == StreamingTranscriptKind.SPEECH_START:
            return [self._partials.on_speech_start()]
        if raw.kind == StreamingTranscriptKind.SPEECH_END:
            return [self._partials.on_speech_end()]
        if raw.kind == StreamingTranscriptKind.PARTIAL:
            return self._partials.on_partial(
                raw.text,
                confidence=raw.confidence,
                language=raw.language,
                start_ms=raw.start_ms,
                end_ms=raw.end_ms,
            )
        if raw.kind == StreamingTranscriptKind.FINAL:
            return self._partials.on_final(
                raw.text,
                confidence=raw.confidence,
                language=raw.language,
                start_ms=raw.start_ms,
                end_ms=raw.end_ms,
            )
        return [raw]
