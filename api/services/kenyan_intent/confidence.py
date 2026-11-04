from __future__ import annotations

from api.services.kenyan_intent.types import BusinessIntent, IntentMatch


class ConfidenceScorer:
    """Score and calibrate intent confidence for realtime voice."""

    def score(
        self,
        *,
        intent: BusinessIntent,
        base_confidence: float,
        matched_phrases: list[str],
        text_length: int,
        is_partial: bool,
        multiple_hits: int,
        language_match: bool = True,
    ) -> float:
        if intent == BusinessIntent.UNKNOWN:
            return 0.0

        score = base_confidence

        if multiple_hits > 1:
            score += min(0.08, 0.03 * (multiple_hits - 1))

        longest = max((len(p) for p in matched_phrases), default=0)
        score += min(0.06, longest / 200.0)

        if text_length < 8 and not is_partial:
            score -= 0.05

        if is_partial:
            score -= 0.08

        if not language_match:
            score -= 0.02

        return max(0.0, min(1.0, score))

    def should_commit(
        self,
        confidence: float,
        *,
        is_partial: bool,
        partial_threshold: float,
        final_threshold: float,
    ) -> bool:
        if is_partial:
            return confidence >= partial_threshold
        return confidence >= final_threshold

    def decay_confidence(self, current: float, decay: float) -> float:
        return max(0.0, current - decay)

    def merge_matches(self, matches: list[IntentMatch]) -> IntentMatch | None:
        if not matches:
            return None
        best = max(matches, key=lambda m: m.confidence)
        return best
