"""Timeout detection and provider failover."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from loguru import logger

from api.services.streaming_stt.config import StreamingSTTConfig
from api.services.streaming_stt.errors import STTTimeoutError


@dataclass
class TimeoutRecoveryManager:
    """Tracks provider health and decides when to reconnect or fall back."""

    config: StreamingSTTConfig
    _last_event_at: float = field(default_factory=time.monotonic)
    _last_audio_at: float = field(default_factory=time.monotonic)
    _reconnect_attempts: int = 0
    _using_fallback: bool = False
    _deepgram_connected: bool = False

    def touch_event(self) -> None:
        self._last_event_at = time.monotonic()

    def touch_audio(self) -> None:
        self._last_audio_at = time.monotonic()

    def mark_connected(self) -> None:
        self._deepgram_connected = True
        self._reconnect_attempts = 0
        self.touch_event()

    def mark_disconnected(self) -> None:
        self._deepgram_connected = False

    def mark_fallback(self) -> None:
        self._using_fallback = True

    def mark_primary_restored(self) -> None:
        self._using_fallback = False
        self._reconnect_attempts = 0

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnect_attempts

    @property
    def deepgram_connected(self) -> bool:
        return self._deepgram_connected

    def last_event_age_ms(self) -> float:
        return (time.monotonic() - self._last_event_at) * 1000.0

    def should_reconnect_deepgram(self) -> bool:
        if self._using_fallback:
            return False
        if self._deepgram_connected:
            return False
        return self._reconnect_attempts < self.config.deepgram_reconnect_attempts

    def record_reconnect_attempt(self) -> None:
        self._reconnect_attempts += 1
        logger.warning(
            "streaming_stt deepgram reconnect attempt {}/{}",
            self._reconnect_attempts,
            self.config.deepgram_reconnect_attempts,
        )

    def should_fallback_to_whisper(self) -> bool:
        if self._using_fallback:
            return False
        if not self.config.fallback_after_reconnect_fail:
            return False
        return self._reconnect_attempts >= self.config.deepgram_reconnect_attempts

    def check_idle_timeout(self) -> None:
        """Raise when audio is flowing but the active provider is silent too long."""
        if self._using_fallback:
            return
        if not self._deepgram_connected:
            return
        audio_age_ms = (time.monotonic() - self._last_audio_at) * 1000.0
        if audio_age_ms > 500 and self.last_event_age_ms() > self.config.deepgram_idle_timeout_s * 1000:
            raise STTTimeoutError(
                f"deepgram idle for {self.last_event_age_ms():.0f}ms while audio active"
            )
