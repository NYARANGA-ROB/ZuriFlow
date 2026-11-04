"""Configuration for call reliability systems."""

from __future__ import annotations

from dataclasses import dataclass

from api.constants import (
    CALL_RELIABILITY_DLQ_TTL_S,
    CALL_RELIABILITY_ENABLED,
    CALL_RELIABILITY_EVENT_TTL_S,
    CALL_RELIABILITY_MAX_RETRIES,
    CALL_RELIABILITY_RETRY_BASE_DELAY_S,
    CALL_RELIABILITY_WS_CHECKPOINT_TTL_S,
)


@dataclass(frozen=True)
class CallReliabilityConfig:
    enabled: bool = CALL_RELIABILITY_ENABLED
    max_retries: int = CALL_RELIABILITY_MAX_RETRIES
    retry_base_delay_s: float = CALL_RELIABILITY_RETRY_BASE_DELAY_S
    event_ttl_s: int = CALL_RELIABILITY_EVENT_TTL_S
    dlq_ttl_s: int = CALL_RELIABILITY_DLQ_TTL_S
    ws_checkpoint_ttl_s: int = CALL_RELIABILITY_WS_CHECKPOINT_TTL_S
    max_events_per_session: int = 2000


DEFAULT_CALL_RELIABILITY_CONFIG = CallReliabilityConfig()
