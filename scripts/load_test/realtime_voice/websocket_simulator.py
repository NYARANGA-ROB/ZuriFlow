"""WebSocket client simulator for realtime audio/voice endpoints."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from scripts.load_test.realtime_voice.protocol import (
    AudioChunkFrame,
    ControlType,
    decode_audio_chunk,
    decode_control,
    encode_audio_chunk,
    encode_control,
)
from scripts.load_test.realtime_voice.audio import generate_pcm_chunk
from scripts.load_test.realtime_voice.benchmark import CallerMetrics, LatencyBenchmark
from scripts.load_test.realtime_voice.config import LoadTestConfig


@dataclass
class WebSocketSimulator:
    """Simulates one caller over the realtime audio WebSocket protocol."""

    config: LoadTestConfig
    caller_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    benchmark: LatencyBenchmark = field(default_factory=LatencyBenchmark)

    _ws: ClientConnection | None = field(default=None, init=False)
    _session_id: str | None = field(default=None, init=False)
    _seq: int = field(default=0, init=False)
    _elapsed_ms: int = field(default=0, init=False)
    _running: bool = field(default=False, init=False)
    _errors: list[str] = field(default_factory=list, init=False)

    @property
    def metrics(self) -> CallerMetrics:
        return self.benchmark.caller_metrics(self.caller_id)

    async def run(self, duration_s: float | None = None) -> CallerMetrics:
        """Connect, handshake, stream audio, collect metrics."""
        duration = duration_s if duration_s is not None else self.config.duration_s
        url = self.config.websocket_url()
        connect_start = time.monotonic()

        try:
            async with asyncio.timeout(self.config.connect_timeout_s):
                self._ws = await websockets.connect(url, open_timeout=self.config.connect_timeout_s)
        except Exception as exc:
            self._errors.append(f"connect: {exc}")
            self.benchmark.record_connect_failure(self.caller_id)
            return self.metrics

        self.benchmark.record_connect_ms(
            self.caller_id, (time.monotonic() - connect_start) * 1000.0
        )

        try:
            await self._handshake()
            self._running = True
            await asyncio.gather(
                self._audio_sender(duration),
                self._receiver_loop(duration),
                return_exceptions=True,
            )
        except Exception as exc:
            self._errors.append(f"session: {exc}")
        finally:
            await self._graceful_close()
            self.benchmark.finalize_caller(self.caller_id, errors=self._errors)
        return self.metrics

    async def _handshake(self) -> None:
        assert self._ws is not None
        hello: dict[str, Any] = {
            "type": ControlType.HELLO.value,
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
            "client_id": f"loadtest-{self.caller_id}",
        }
        meta = self.config.hello_metadata()
        if meta:
            hello["metadata"] = meta

        hs_start = time.monotonic()
        await self._ws.send(json.dumps(hello, separators=(",", ":")))
        raw = await asyncio.wait_for(self._ws.recv(), timeout=self.config.connect_timeout_s)
        if isinstance(raw, bytes):
            raise RuntimeError("expected hello_ack text frame")
        ack = decode_control(raw)
        if ack.get("type") != ControlType.HELLO_ACK.value:
            raise RuntimeError(f"unexpected handshake response: {ack}")
        self._session_id = str(ack.get("session_id", ""))
        self.benchmark.record_handshake_ms(
            self.caller_id, (time.monotonic() - hs_start) * 1000.0
        )

    async def _audio_sender(self, duration_s: float) -> None:
        if not self.config.send_audio:
            await asyncio.sleep(duration_s)
            return

        assert self._ws is not None
        interval = self.config.chunk_ms / 1000.0
        deadline = time.monotonic() + duration_s
        chunks_sent = 0

        while self._running and time.monotonic() < deadline:
            loop_start = time.monotonic()
            pcm = generate_pcm_chunk(
                sequence=self._seq,
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                chunk_ms=self.config.chunk_ms,
                pattern=self.config.speech_pattern,
            )
            frame = AudioChunkFrame(
                sequence=self._seq,
                timestamp_ms=self._elapsed_ms,
                pcm=pcm,
            )
            await self._ws.send(encode_audio_chunk(frame))
            self.benchmark.record_chunk_sent(self.caller_id)
            self._seq += 1
            self._elapsed_ms += self.config.chunk_ms
            chunks_sent += 1

            sleep_for = interval - (time.monotonic() - loop_start)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

        self.benchmark.record_sender_done(self.caller_id, chunks_sent)

    async def _receiver_loop(self, duration_s: float) -> None:
        assert self._ws is not None
        deadline = time.monotonic() + duration_s + 2.0
        last_ping = time.monotonic()

        while self._running and time.monotonic() < deadline:
            timeout = min(1.0, deadline - time.monotonic())
            if timeout <= 0:
                break
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                if (
                    self.config.heartbeat_interval_s > 0
                    and time.monotonic() - last_ping >= self.config.heartbeat_interval_s
                ):
                    await self._send_ping()
                    last_ping = time.monotonic()
                continue

            if isinstance(raw, str):
                await self._handle_control(raw)
            elif isinstance(raw, bytes) and self.config.drain_outbound:
                await self._handle_audio(raw)

    async def _handle_control(self, text: str) -> None:
        msg = decode_control(text)
        msg_type = msg.get("type")
        if msg_type == ControlType.PONG.value:
            client_ts = msg.get("ts")
            if client_ts is not None:
                rtt = max(0.0, (time.time() - float(client_ts)) * 1000.0)
                self.benchmark.record_ws_rtt(self.caller_id, rtt)
        elif msg_type == ControlType.PING.value:
            await self._send_pong(msg.get("ts"))
        elif msg_type == ControlType.ERROR.value:
            self._errors.append(f"server_error: {msg.get('message', msg)}")

    async def _handle_audio(self, data: bytes) -> None:
        try:
            frame = decode_audio_chunk(data)
            self.benchmark.record_outbound_audio(
                self.caller_id, len(frame.pcm), frame.sequence
            )
        except Exception as exc:
            self._errors.append(f"decode_audio: {exc}")

    async def _send_ping(self) -> None:
        assert self._ws is not None
        await self._ws.send(encode_control(ControlType.PING, ts=time.time()))

    async def _send_pong(self, ts: Any) -> None:
        assert self._ws is not None
        await self._ws.send(encode_control(ControlType.PONG, ts=ts, server_ts=time.time()))

    async def _graceful_close(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.send(
                    encode_control(ControlType.DISCONNECT, reason="load_test_done")
                )
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
