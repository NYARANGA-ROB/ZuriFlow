"""Types for voice cost optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TurnComplexity(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


class ModelTier(str, Enum):
    SMALL = "small"
    STANDARD = "standard"
    LARGE = "large"


class ResponseSource(str, Enum):
    PRERECORDED = "prerecorded"
    CACHE = "cache"
    LLM = "llm"


@dataclass(frozen=True)
class RoutingDecision:
    complexity: TurnComplexity
    model_tier: ModelTier
    max_output_tokens: int
    reason: str
    skip_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "complexity": self.complexity.value,
            "model_tier": self.model_tier.value,
            "max_output_tokens": self.max_output_tokens,
            "reason": self.reason,
            "skip_llm": self.skip_llm,
        }


@dataclass
class HybridResolution:
    source: ResponseSource
    text: str = ""
    routing: RoutingDecision | None = None
    cache_key: str = ""
    prerecorded_key: str = ""
    tts_cached: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "text": self.text,
            "routing": self.routing.to_dict() if self.routing else None,
            "cache_key": self.cache_key,
            "prerecorded_key": self.prerecorded_key,
            "tts_cached": self.tts_cached,
            "metadata": dict(self.metadata),
        }


@dataclass
class TokenUsageRecord:
    session_id: str
    organization_id: int
    workflow_run_id: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    llm_calls: int = 0
    tts_characters: int = 0
    cache_hits: int = 0
    prerecorded_hits: int = 0
    tokens_saved: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "llm_calls": self.llm_calls,
            "tts_characters": self.tts_characters,
            "cache_hits": self.cache_hits,
            "prerecorded_hits": self.prerecorded_hits,
            "tokens_saved": self.tokens_saved,
        }


@dataclass
class CostAnalyticsSnapshot:
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    total_sessions: int = 0
    llm_calls: int = 0
    cache_hits: int = 0
    prerecorded_hits: int = 0
    tts_characters: int = 0
    tts_generations_avoided: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_saved: int = 0
    estimated_cost_usd: float = 0.0
    estimated_savings_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "from_ts": self.from_ts,
            "to_ts": self.to_ts,
            "generated_at": self.generated_at,
            "total_sessions": self.total_sessions,
            "llm_calls": self.llm_calls,
            "cache_hits": self.cache_hits,
            "prerecorded_hits": self.prerecorded_hits,
            "tts_characters": self.tts_characters,
            "tts_generations_avoided": self.tts_generations_avoided,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_saved": self.tokens_saved,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "estimated_savings_usd": round(self.estimated_savings_usd, 4),
        }
