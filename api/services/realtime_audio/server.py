"""WebSocket session runner — bidirectional streaming with heartbeat."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from starlette.websockets import WebSocketState

from api.services.realtime_audio.chunks import AudioChunkHandler
from api.services.realtime_audio.config import RealtimeAudioConfig, DEFAULT_CONFIG
from api.services.realtime_audio.connection_manager import (
    AudioSession,
    RealtimeAudioConnectionManager,
    get_connection_manager,
)
from api.services.realtime_audio.errors import (
    HeartbeatTimeoutError,
    ProtocolError,
    RealtimeAudioError,
    SessionExpiredError,
    SessionNotFoundError,
)
from api.services.realtime_audio.logging import (
    log_error,
    log_heartbeat,
    session_log_context,
)
from api.services.realtime_audio.protocol import (
    ControlType,
    decode_audio_chunk,
    decode_control,
    encode_audio_chunk,
    encode_control,
)


class RealtimeAudioWebSocketServer:
    """Runs one WebSocket connection as three cooperative asyncio tasks."""

    def __init__(
        self,
        websocket: WebSocket,
        manager: RealtimeAudioConnectionManager | None = None,
        config: RealtimeAudioConfig = DEFAULT_CONFIG,
        *,
        organization_id: int | None = None,
        on_session_ready: Callable[[AudioSession], Awaitable[None]] | None = None,
    ) -> None:
        self._ws = websocket
        self._manager = manager or get_connection_manager()
        self._config = config
        self._organization_id = organization_id
        self._on_session_ready = on_session_ready
        self._session: AudioSession | None = None
        self._handshake_resumed = False
        self._pipeline_task: asyncio.Task | None = None
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._last_pong_at = time.monotonic()

    @property
    def session(self) -> AudioSession | None:
        return self._session

    async def run(self) -> None:
        await self._manager.start()
        handshake_started = time.perf_counter()
        await self._ws.accept()

        try:
            await self._handshake()
            try:
                from api.services.realtime_observability.collector import (
                    VoiceObservabilityCollector,
                )

                VoiceObservabilityCollector.record_ws_handshake(
                    (time.perf_counter() - handshake_started) * 1000.0
                )
            except Exception:
                pass
            assert self._session is not None
            with session_log_context(
                self._session.session_id,
                client_id=self._session.client_id,
            ):
                if self._on_session_ready is not None:
                    self._pipeline_task = asyncio.create_task(
                        self._run_session_ready(self._session, self._handshake_resumed),
                        name="ra-session-ready",
                    )
                self._tasks = [
                    asyncio.create_task(self._receiver_loop(), name="ra-receiver"),
                    asyncio.create_task(self._sender_loop(), name="ra-sender"),
                    asyncio.create_task(self._heartbeat_loop(), name="ra-heartbeat"),
                ]
                await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in self._tasks:
                    if task.done() and not task.cancelled():
                        exc = task.exception()
                        if exc:
                            raise exc
        except WebSocketDisconnect as e:
            await self._graceful_shutdown(
                reason=f"websocket_disconnect code={e.code}",
                ws_code=e.code or 1000,
            )
        except HeartbeatTimeoutError as e:
            await self._graceful_shutdown(reason=str(e), ws_code=4000)
        except (ProtocolError, SessionNotFoundError, SessionExpiredError) as e:
            await self._send_error(e.code, str(e))
            await self._graceful_shutdown(reason=str(e), ws_code=1008)
        except RealtimeAudioError as e:
            await self._send_error(e.code, str(e))
            await self._graceful_shutdown(reason=str(e), ws_code=1011)
        except Exception as e:
            log_error(self._session.session_id if self._session else "-", str(e), exc=e)
            await self._graceful_shutdown(reason="internal_error", ws_code=1011)
        finally:
            await self._cancel_tasks()
            if self._pipeline_task and not self._pipeline_task.done():
                self._pipeline_task.cancel()
                await asyncio.gather(self._pipeline_task, return_exceptions=True)

    async def _run_session_ready(self, session: AudioSession, resumed: bool) -> None:
        assert self._on_session_ready is not None
        try:
            await self._on_session_ready(session, resumed=resumed)
        except TypeError:
            await self._on_session_ready(session)
        except Exception as e:
            log_error(session.session_id, f"session_ready failed: {e}", exc=e)
            await self._send_error("pipeline_start_failed", str(e))
            self._stop.set()

    async def _handshake(self) -> None:
        raw = await asyncio.wait_for(
            self._ws.receive_text(),
            timeout=self._config.heartbeat_timeout_s,
        )
        msg = decode_control(raw)
        msg_type = msg.get("type")

        if msg_type == ControlType.HELLO.value:
            self._handshake_resumed = False
            metadata = dict(msg.get("metadata") or {})
            if self._organization_id:
                metadata["organization_id"] = self._organization_id
            self._session = await self._manager.create_session(
                sample_rate=int(msg.get("sample_rate", self._config.default_sample_rate)),
                channels=int(msg.get("channels", self._config.default_channels)),
                client_id=msg.get("client_id"),
                metadata=metadata,
            )
            if self._organization_id:
                from api.services.tenant.session_tenant import register_session_organization

                await register_session_organization(
                    self._session.session_id, self._organization_id
                )
            await self._ws.send_text(
                encode_control(
                    ControlType.HELLO_ACK,
                    session_id=self._session.session_id,
                    reconnect_token=self._session.reconnect_token,
                    sample_rate=self._session.sample_rate,
                    channels=self._session.channels,
                    max_chunk_bytes=self._config.max_chunk_bytes,
                )
            )
            return

        if msg_type == ControlType.RECONNECT.value:
            self._handshake_resumed = True
            session_id = str(msg.get("session_id", ""))
            token = str(msg.get("reconnect_token", ""))
            last_ack = int(msg.get("last_ack_seq", -1))
            self._session = await self._manager.resume_session(
                session_id=session_id,
                reconnect_token=token,
                last_ack_seq=last_ack,
                client_id=msg.get("client_id"),
            )
            await self._ws.send_text(
                encode_control(
                    ControlType.HELLO_ACK,
                    session_id=self._session.session_id,
                    reconnect_token=self._session.reconnect_token,
                    resumed=True,
                    last_ack_seq=self._session.chunks.last_inbound_ack,
                )
            )
            return

        raise ProtocolError("first frame must be hello or reconnect")

    async def _receiver_loop(self) -> None:
        session = self._require_session()
        while not self._stop.is_set():
            message = await self._ws.receive()
            session.touch()

            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            if "text" in message and message["text"] is not None:
                await self._handle_control(message["text"])
                continue

            if "bytes" in message and message["bytes"] is not None:
                await self._handle_binary(message["bytes"])
                continue

    async def _handle_control(self, text: str) -> None:
        session = self._require_session()
        msg = decode_control(text)
        msg_type = msg.get("type")

        if msg_type == ControlType.PING.value:
            client_ts = msg.get("ts")
            if client_ts is not None:
                try:
                    from api.services.realtime_observability.collector import (
                        VoiceObservabilityCollector,
                    )

                    latency_ms = max(0.0, (time.time() - float(client_ts)) * 1000.0)
                    VoiceObservabilityCollector.record_ws_roundtrip(latency_ms)
                except (TypeError, ValueError):
                    pass
            await self._ws.send_text(
                encode_control(ControlType.PONG, ts=client_ts, server_ts=time.time())
            )
            self._last_pong_at = time.monotonic()
            log_heartbeat(session.session_id, event="pong")
            return

        if msg_type == ControlType.PONG.value:
            self._last_pong_at = time.monotonic()
            log_heartbeat(session.session_id, event="client_pong")
            return

        if msg_type == ControlType.DISCONNECT.value:
            reason = msg.get("reason", "client_requested")
            self._stop.set()
            await self._graceful_shutdown(reason=reason, ws_code=1000)
            return

        if msg_type == ControlType.AUDIO_ACK.value:
            session.chunks.ack_inbound(int(msg.get("seq", -1)))
            return

        raise ProtocolError(f"unsupported control type: {msg_type}")

    async def _handle_binary(self, data: bytes) -> None:
        session = self._require_session()
        if len(data) > self._config.ws_max_message_size:
            raise ProtocolError("binary frame exceeds max message size")

        frame = decode_audio_chunk(data)
        chunk = session.chunks.ingest_client_chunk(frame.pcm, client_seq=frame.sequence)
        await session.queues.inbound.put(chunk, drop_if_full=True)

    async def _sender_loop(self) -> None:
        session = self._require_session()
        async for chunk in session.queues.outbound.iter_chunks():
            if self._stop.is_set():
                break
            if self._ws.client_state != WebSocketState.CONNECTED:
                break
            payload = encode_audio_chunk(chunk)
            await self._ws.send_bytes(payload)

    async def _heartbeat_loop(self) -> None:
        session = self._require_session()
        while not self._stop.is_set():
            await asyncio.sleep(self._config.server_ping_interval_s)
            if self._stop.is_set():
                break

            elapsed = time.monotonic() - self._last_pong_at
            if elapsed > self._config.heartbeat_timeout_s:
                raise HeartbeatTimeoutError(session.session_id)

            if self._ws.client_state == WebSocketState.CONNECTED:
                await self._ws.send_text(
                    encode_control(ControlType.PING, ts=time.time())
                )
                log_heartbeat(session.session_id, event="ping")

    async def _send_error(self, code: str, message: str) -> None:
        if self._ws.client_state == WebSocketState.CONNECTED:
            try:
                await self._ws.send_text(
                    encode_control(ControlType.ERROR, code=code, message=message)
                )
            except Exception:
                pass

    async def _graceful_shutdown(self, *, reason: str, ws_code: int) -> None:
        if self._stop.is_set():
            return
        self._stop.set()

        session_id = self._session.session_id if self._session else None
        if self._ws.client_state == WebSocketState.CONNECTED:
            try:
                await self._ws.send_text(
                    encode_control(ControlType.DISCONNECT, reason=reason)
                )
            except Exception:
                pass
            try:
                await self._ws.close(code=ws_code, reason=reason[:120])
            except Exception:
                pass

        if session_id:
            await self._manager.release_session(
                session_id, reason=reason, graceful=ws_code == 1000
            )

    async def _cancel_tasks(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def _require_session(self) -> AudioSession:
        if self._session is None:
            raise ProtocolError("session not established")
        return self._session


async def enqueue_outbound_pcm(
    session: AudioSession,
    pcm: bytes,
    *,
    handler: AudioChunkHandler | None = None,
) -> bool:
    """Helper for pipeline code to push synthesized audio to the client."""
    chunk_handler = handler or session.chunks
    frame = chunk_handler.next_outbound_chunk(pcm)
    return await session.queues.outbound.put(frame, drop_if_full=True)


async def drain_inbound_audio(session: AudioSession):
    """Async iterator for downstream consumers (STT, pipeline, etc.)."""
    async for chunk in session.queues.inbound.iter_chunks():
        yield chunk
