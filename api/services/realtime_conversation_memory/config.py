"""Configuration for realtime conversation memory."""

from __future__ import annotations

from dataclasses import dataclass

from api.constants import (
    REALTIME_MEMORY_ENABLED,
    REALTIME_MEMORY_MAX_TURNS,
    REALTIME_MEMORY_PAUSE_RECOVERY_S,
    REALTIME_MEMORY_SUMMARY_MAX_CHARS,
)


@dataclass(frozen=True)
class RealtimeMemoryConfig:
    enabled: bool = REALTIME_MEMORY_ENABLED
    max_turns: int = REALTIME_MEMORY_MAX_TURNS
    max_summary_chars: int = REALTIME_MEMORY_SUMMARY_MAX_CHARS
    pause_recovery_s: float = REALTIME_MEMORY_PAUSE_RECOVERY_S
    intent_confidence_decay: float = 0.15
    retrieval_timeout_ms: float = 10.0
    inject_context_as_system_hint: bool = True


DEFAULT_MEMORY_CONFIG = RealtimeMemoryConfig()
