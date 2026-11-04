"""Configuration for voice cost optimization."""

from __future__ import annotations

from dataclasses import dataclass

from api.constants import (
    VOICE_COST_CACHE_TTL_S,
    VOICE_COST_COMPLEX_MAX_TOKENS,
    VOICE_COST_OPTIMIZATION_ENABLED,
    VOICE_COST_SIMPLE_MAX_TOKENS,
    VOICE_COST_STANDARD_MAX_TOKENS,
)


@dataclass(frozen=True)
class VoiceCostConfig:
    enabled: bool = VOICE_COST_OPTIMIZATION_ENABLED
    cache_ttl_s: int = VOICE_COST_CACHE_TTL_S
    simple_max_tokens: int = VOICE_COST_SIMPLE_MAX_TOKENS
    standard_max_tokens: int = VOICE_COST_STANDARD_MAX_TOKENS
    complex_max_tokens: int = VOICE_COST_COMPLEX_MAX_TOKENS
    cache_max_entries_per_org: int = 2000
    tts_dedup_enabled: bool = True
    prerecorded_enabled: bool = True
    response_cache_enabled: bool = True

    # Rough USD per 1M tokens for cost estimates (gpt-4o-mini class).
    input_cost_per_million: float = 0.15
    output_cost_per_million: float = 0.60
    # ~$0.015 per 1k chars (ElevenLabs scale estimate)
    tts_cost_per_1k_chars: float = 0.015


DEFAULT_VOICE_COST_CONFIG = VoiceCostConfig()
