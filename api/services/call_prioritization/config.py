"""Configuration for call prioritization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PrioritizationWeights:
    payment: float = 0.35
    answer_rate: float = 0.30
    engagement: float = 0.20
    escalation_penalty: float = 0.15
    failure_penalty: float = 0.10


@dataclass
class RetryPolicy:
    base_delay_s: int = 3600
    max_delay_s: int = 86400 * 7
    max_attempts: int = 6
    high_score_multiplier: float = 0.5
    low_score_multiplier: float = 1.5
    likely_payer_threshold: float = 65.0
    deprioritize_threshold: float = 25.0


@dataclass
class CallPrioritizationConfig:
    enabled: bool = True
    queue_ttl_s: int = 86400
    weights: PrioritizationWeights = field(default_factory=PrioritizationWeights)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    min_score_to_call: float = 15.0

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> CallPrioritizationConfig:
        if not raw:
            return cls()
        weights_raw = raw.get("weights") or {}
        retry_raw = raw.get("retry") or {}
        return cls(
            enabled=bool(raw.get("enabled", True)),
            queue_ttl_s=int(raw.get("queue_ttl_s", 86400)),
            min_score_to_call=float(raw.get("min_score_to_call", 15.0)),
            weights=PrioritizationWeights(
                payment=float(weights_raw.get("payment", 0.35)),
                answer_rate=float(weights_raw.get("answer_rate", 0.30)),
                engagement=float(weights_raw.get("engagement", 0.20)),
                escalation_penalty=float(weights_raw.get("escalation_penalty", 0.15)),
                failure_penalty=float(weights_raw.get("failure_penalty", 0.10)),
            ),
            retry=RetryPolicy(
                base_delay_s=int(retry_raw.get("base_delay_s", 3600)),
                max_delay_s=int(retry_raw.get("max_delay_s", 86400 * 7)),
                max_attempts=int(retry_raw.get("max_attempts", 6)),
                high_score_multiplier=float(retry_raw.get("high_score_multiplier", 0.5)),
                low_score_multiplier=float(retry_raw.get("low_score_multiplier", 1.5)),
                likely_payer_threshold=float(retry_raw.get("likely_payer_threshold", 65.0)),
                deprioritize_threshold=float(retry_raw.get("deprioritize_threshold", 25.0)),
            ),
        )


DEFAULT_PRIORITIZATION_CONFIG = CallPrioritizationConfig()
ORG_CONFIG_KEY = "CALL_PRIORITIZATION_CONFIGURATION"
