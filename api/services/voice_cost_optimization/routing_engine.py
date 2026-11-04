"""Intelligent routing — classify turns and select model/token budgets."""

from __future__ import annotations

import re

from api.services.voice_cost_optimization.config import VoiceCostConfig, DEFAULT_VOICE_COST_CONFIG
from api.services.voice_cost_optimization.types import ModelTier, RoutingDecision, TurnComplexity

_SIMPLE_PATTERNS = re.compile(
    r"^(hi|hello|hey|habari|yes|no|sawa|ndio|hapana|thanks|thank you|asante|bye|"
    r"goodbye|kwaheri|ok|okay)\.?$",
    re.IGNORECASE,
)

_COMPLEX_PATTERNS = re.compile(
    r"\b(negotiat|installment|payment plan|lawyer|court|complain|dispute|"
    r"refund|fraud|harass|escalat|supervisor|manager|legal|sue|"
    r"malipo|mpango|deni|wakili|malalamiko)\b",
    re.IGNORECASE,
)


class IntelligentRoutingEngine:
    """Route simple calls to smaller token budgets; reserve capacity for complex turns."""

    def __init__(self, config: VoiceCostConfig | None = None) -> None:
        self._config = config or DEFAULT_VOICE_COST_CONFIG

    def classify(
        self,
        user_text: str,
        *,
        turn_count: int = 0,
        intent: str = "",
        intent_confidence: float = 0.0,
    ) -> RoutingDecision:
        text = user_text.strip()
        word_count = len(text.split())

        if intent and intent_confidence >= 0.85 and intent in (
            "greeting",
            "goodbye",
            "thanks",
            "payment_confirmed",
        ):
            return RoutingDecision(
                complexity=TurnComplexity.SIMPLE,
                model_tier=ModelTier.SMALL,
                max_output_tokens=self._config.simple_max_tokens,
                reason="high_confidence_simple_intent",
                skip_llm=True,
            )

        if word_count <= 4 and _SIMPLE_PATTERNS.match(text):
            return RoutingDecision(
                complexity=TurnComplexity.SIMPLE,
                model_tier=ModelTier.SMALL,
                max_output_tokens=self._config.simple_max_tokens,
                reason="short_acknowledgement",
                skip_llm=True,
            )

        if _COMPLEX_PATTERNS.search(text) or word_count > 35 or turn_count > 12:
            return RoutingDecision(
                complexity=TurnComplexity.COMPLEX,
                model_tier=ModelTier.LARGE,
                max_output_tokens=self._config.complex_max_tokens,
                reason="complex_topic_or_long_conversation",
            )

        if word_count <= 12 and not _COMPLEX_PATTERNS.search(text):
            return RoutingDecision(
                complexity=TurnComplexity.SIMPLE,
                model_tier=ModelTier.SMALL,
                max_output_tokens=self._config.simple_max_tokens,
                reason="short_simple_utterance",
            )

        return RoutingDecision(
            complexity=TurnComplexity.STANDARD,
            model_tier=ModelTier.STANDARD,
            max_output_tokens=self._config.standard_max_tokens,
            reason="default_standard",
        )


_engine: IntelligentRoutingEngine | None = None


def get_intelligent_routing_engine() -> IntelligentRoutingEngine:
    global _engine
    if _engine is None:
        _engine = IntelligentRoutingEngine()
    return _engine
