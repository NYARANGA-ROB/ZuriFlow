"""Realtime audio streaming errors."""

from __future__ import annotations


class RealtimeAudioError(Exception):
    """Base error for the realtime audio server."""

    def __init__(self, message: str, *, code: str = "internal_error") -> None:
        super().__init__(message)
        self.code = code


class ProtocolError(RealtimeAudioError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="protocol_error")


class SessionNotFoundError(RealtimeAudioError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session not found: {session_id}", code="session_not_found")
        self.session_id = session_id


class SessionExpiredError(RealtimeAudioError):
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Reconnect window expired for session: {session_id}",
            code="session_expired",
        )
        self.session_id = session_id


class QueueBackpressureError(RealtimeAudioError):
    def __init__(self, direction: str) -> None:
        super().__init__(
            f"{direction} queue saturated — chunk dropped",
            code="queue_saturated",
        )
        self.direction = direction


class HeartbeatTimeoutError(RealtimeAudioError):
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Heartbeat timeout for session: {session_id}",
            code="heartbeat_timeout",
        )
        self.session_id = session_id
