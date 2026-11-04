"""Connection lifecycle, reconnect grace, and session registry."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from api.services.realtime_audio.chunks import AudioChunkHandler
from api.services.realtime_audio.config import RealtimeAudioConfig, DEFAULT_CONFIG
from api.services.realtime_audio.errors import SessionExpiredError, SessionNotFoundError
from api.services.realtime_audio.logging import log_connect, log_disconnect
from api.services.realtime_observability.collector import VoiceObservabilityCollector
from api.services.realtime_audio.queues import BidirectionalStreamQueues

# Callback invoked for each inbound chunk (e.g. pipeline STT). Non-blocking.
InboundChunkHandler = Callable[["AudioSession"], Awaitable[None]]


@dataclass
class AudioSession:
    """Mutable session state shared across reconnects within the grace window."""

    session_id: str
    client_id: str | None
    sample_rate: int
    channels: int
    config: RealtimeAudioConfig
    queues: BidirectionalStreamQueues
    chunks: AudioChunkHandler
    created_at: float = field(default_factory=time.monotonic)
    last_seen_at: float = field(default_factory=time.monotonic)
    disconnected_at: float | None = None
    reconnect_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_seen_at = time.monotonic()

    def mark_disconnected(self) -> None:
        self.active = False
        self.disconnected_at = time.monotonic()

    def within_reconnect_grace(self) -> bool:
        if self.disconnected_at is None:
            return True
        return (time.monotonic() - self.disconnected_at) <= self.config.reconnect_grace_s


@dataclass
class _SessionSlot:
    session: AudioSession
    cleanup_task: asyncio.Task | None = None


class RealtimeAudioConnectionManager:
    """Registry of live and grace-period sessions with bounded fan-out."""

    def __init__(self, config: RealtimeAudioConfig = DEFAULT_CONFIG) -> None:
        self._config = config
        self._sessions: dict[str, _SessionSlot] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task | None = None
        self._session_removed_callbacks: list[Callable[[str], Awaitable[None]]] = []

    def register_on_session_removed(
        self, callback: Callable[[str], Awaitable[None]]
    ) -> None:
        if callback not in self._session_removed_callbacks:
            self._session_removed_callbacks.append(callback)

    def session_in_grace(self, session_id: str) -> bool:
        slot = self._sessions.get(session_id)
        if slot is None:
            return False
        return not slot.session.active and slot.session.within_reconnect_grace()

    async def _notify_session_removed(self, session_id: str) -> None:
        for callback in self._session_removed_callbacks:
            try:
                await callback(session_id)
            except Exception as e:
                logger.warning(
                    "session_removed callback failed session_id={}: {}",
                    session_id[:8],
                    e,
                )

    async def start(self) -> None:
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(
                self._reap_expired_sessions(), name="realtime-audio-reaper"
            )

    def is_running(self) -> bool:
        return self._reaper_task is not None and not self._reaper_task.done()

    def session_count(self) -> int:
        return len(self._sessions)

    def snapshot_sessions(self) -> list[dict[str, Any]]:
        """Best-effort snapshot of live audio sessions for admin dashboards."""
        rows: list[dict[str, Any]] = []
        for session_id, slot in self._sessions.items():
            session = slot.session
            rows.append(
                {
                    "session_id": session_id,
                    "active": session.active,
                    "client_id": session.client_id,
                    "in_grace": not session.active and session.within_reconnect_grace(),
                    "metadata": dict(session.metadata),
                    "created_at": session.created_at,
                    "last_seen_at": session.last_seen_at,
                }
            )
        return rows

    async def stop(self) -> None:
        if self._reaper_task:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None

        async with self._lock:
            session_ids = list(self._sessions.keys())
        for sid in session_ids:
            await self.remove_session(sid, reason="server_shutdown", graceful=True)

    async def create_session(
        self,
        *,
        sample_rate: int | None = None,
        channels: int | None = None,
        client_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AudioSession:
        async with self._lock:
            if len(self._sessions) >= self._config.max_sessions:
                raise RuntimeError("maximum realtime audio sessions reached")

            session_id = uuid.uuid4().hex
            rate = sample_rate or self._config.default_sample_rate
            ch = channels or self._config.default_channels

            session = AudioSession(
                session_id=session_id,
                client_id=client_id,
                sample_rate=rate,
                channels=ch,
                config=self._config,
                queues=BidirectionalStreamQueues(session_id, self._config),
                chunks=AudioChunkHandler(
                    session_id=session_id,
                    sample_rate=rate,
                    channels=ch,
                    config=self._config,
                ),
                metadata=dict(metadata or {}),
            )
            self._sessions[session_id] = _SessionSlot(session=session)
            log_connect(session_id, client_id=client_id, resumed=False)
            VoiceObservabilityCollector.record_ws_connect(
                endpoint="realtime_audio",
                session_id=session_id,
                resumed=False,
            )
            return session

    async def resume_session(
        self,
        *,
        session_id: str,
        reconnect_token: str,
        last_ack_seq: int = -1,
        client_id: str | None = None,
    ) -> AudioSession:
        async with self._lock:
            slot = self._sessions.get(session_id)
            if slot is None:
                raise SessionNotFoundError(session_id)
            session = slot.session
            if session.reconnect_token != reconnect_token:
                raise SessionNotFoundError(session_id)
            if not session.within_reconnect_grace():
                await self._finalize_slot(session_id, slot)
                raise SessionExpiredError(session_id)

            if slot.cleanup_task and not slot.cleanup_task.done():
                slot.cleanup_task.cancel()

            session.active = True
            session.disconnected_at = None
            session.touch()
            if client_id:
                session.client_id = client_id
            session.chunks.resume_from(last_ack_seq)
            log_connect(session_id, client_id=session.client_id, resumed=True)
            VoiceObservabilityCollector.record_ws_connect(
                endpoint="realtime_audio",
                session_id=session_id,
                resumed=True,
            )
            return session

    async def get_session(self, session_id: str) -> AudioSession:
        async with self._lock:
            slot = self._sessions.get(session_id)
            if slot is None or not slot.session.active:
                raise SessionNotFoundError(session_id)
            slot.session.touch()
            return slot.session

    async def release_session(
        self,
        session_id: str,
        *,
        reason: str = "client_disconnect",
        graceful: bool = True,
    ) -> None:
        async with self._lock:
            slot = self._sessions.get(session_id)
            if slot is None:
                return
            slot.session.mark_disconnected()
            log_disconnect(session_id, reason=reason, graceful=graceful)
            VoiceObservabilityCollector.record_ws_disconnect(
                endpoint="realtime_audio",
                session_id=session_id,
                reason=reason,
            )
            if slot.cleanup_task and not slot.cleanup_task.done():
                return
            slot.cleanup_task = asyncio.create_task(
                self._delayed_remove(session_id, self._config.reconnect_grace_s),
                name=f"realtime-audio-cleanup-{session_id[:8]}",
            )

    async def remove_session(
        self,
        session_id: str,
        *,
        reason: str,
        graceful: bool = True,
    ) -> None:
        async with self._lock:
            slot = self._sessions.pop(session_id, None)
        if slot is None:
            return
        if slot.cleanup_task and not slot.cleanup_task.done():
            slot.cleanup_task.cancel()
        await slot.session.queues.close()
        slot.session.mark_disconnected()
        log_disconnect(session_id, reason=reason, graceful=graceful)
        await self._notify_session_removed(session_id)

    async def _delayed_remove(self, session_id: str, delay_s: float) -> None:
        try:
            await asyncio.sleep(delay_s)
            async with self._lock:
                slot = self._sessions.get(session_id)
                if slot is None or slot.session.active:
                    return
                if slot.session.within_reconnect_grace():
                    return
                self._sessions.pop(session_id, None)
            await slot.session.queues.close()
            await self._notify_session_removed(session_id)
            logger.debug("realtime_audio session expired session_id={}", session_id)
        except asyncio.CancelledError:
            pass

    async def _finalize_slot(self, session_id: str, slot: _SessionSlot) -> None:
        self._sessions.pop(session_id, None)
        if slot.cleanup_task and not slot.cleanup_task.done():
            slot.cleanup_task.cancel()
        await slot.session.queues.close()
        await self._notify_session_removed(session_id)

    async def _reap_expired_sessions(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._config.reconnect_grace_s)
                expired: list[str] = []
                async with self._lock:
                    for sid, slot in self._sessions.items():
                        if not slot.session.active and not slot.session.within_reconnect_grace():
                            expired.append(sid)
                for sid in expired:
                    await self.remove_session(sid, reason="grace_expired", graceful=True)
            except asyncio.CancelledError:
                break


# Process-wide singleton — started from route lifespan or first connection.
_manager: RealtimeAudioConnectionManager | None = None


def get_connection_manager() -> RealtimeAudioConnectionManager:
    global _manager
    if _manager is None:
        _manager = RealtimeAudioConnectionManager()
    return _manager
