from __future__ import annotations

import re
import time
from typing import Callable

from api.services.kenyan_intent.confidence import ConfidenceScorer
from api.services.kenyan_intent.config import KenyanIntentConfig
from api.services.kenyan_intent.patterns import INTENT_PATTERNS, SWAHILI_MARKERS
from api.services.kenyan_intent.types import BusinessIntent, ClassificationResult, IntentMatch

_SLOT_PATTERNS = {
    "amount": re.compile(r"\b(\d[\d,]*)\s*(?:ksh|kes|shillings?|bob)?\b", re.I),
    "phone": re.compile(r"\b(?:\+?254|0)?(?:7|1)\d{8}\b"),
    "date": re.compile(
        r"\b(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|tomorrow|kesho|leo|today|monday|tuesday|wednesday|thursday|friday)\b",
        re.I,
    ),
    "time": re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", re.I),
    "account_ref": re.compile(
        r"\b(?:account|acc(?:ount)?|ref(?:erence)?)\s*(?:number|no\.?)?\s*[:#]?\s*(\w+)\b",
        re.I,
    ),
}


class KenyanIntentClassifier:
    """Low-latency rule-based classifier for Kenyan business voice intents."""

    def __init__(
        self,
        config: KenyanIntentConfig | None = None,
        *,
        normalizer: Callable[[str], str] | None = None,
        scorer: ConfidenceScorer | None = None,
    ) -> None:
        self._config = config or KenyanIntentConfig()
        self._normalizer = normalizer
        self._scorer = scorer or ConfidenceScorer()

    @property
    def scorer(self) -> ConfidenceScorer:
        return self._scorer

    def classify(
        self,
        text: str,
        *,
        is_partial: bool = False,
        prior_intent: BusinessIntent = BusinessIntent.UNKNOWN,
        prior_confidence: float = 0.0,
    ) -> ClassificationResult:
        start = time.perf_counter()
        original = text.strip()
        if not original:
            return ClassificationResult(
                intent=BusinessIntent.UNKNOWN,
                confidence=0.0,
                original_text=original,
                is_partial=is_partial,
            )

        normalized = original
        if self._config.use_normalization and self._normalizer:
            normalized = self._normalizer(original)

        lowered = f"{original} {normalized}".lower()
        language = self._detect_language(lowered)

        matches: list[IntentMatch] = []
        phrase_hits: dict[BusinessIntent, list[str]] = {}

        from api.services.kenyan_intent.learned_patterns import merged_intent_patterns

        patterns_map = merged_intent_patterns()
        for intent, patterns in patterns_map.items():
            intent_score = 0.0
            hits: list[str] = []
            for pattern in patterns:
                if pattern.phrase in lowered:
                    hits.append(pattern.phrase)
                    intent_score = max(intent_score, pattern.weight)
            if hits:
                phrase_hits[intent] = hits
                matches.append(
                    IntentMatch(
                        intent=intent,
                        confidence=intent_score,
                        matched_phrases=hits,
                        language=language,
                    )
                )

        best = self._scorer.merge_matches(matches)
        if best is None:
            intent = prior_intent if prior_intent != BusinessIntent.UNKNOWN else BusinessIntent.UNKNOWN
            confidence = (
                self._scorer.decay_confidence(prior_confidence, self._config.intent_confidence_decay)
                if intent != BusinessIntent.UNKNOWN
                else 0.0
            )
            matched: list[str] = []
        else:
            intent = best.intent
            matched = phrase_hits.get(intent, [])
            confidence = self._scorer.score(
                intent=intent,
                base_confidence=best.confidence,
                matched_phrases=matched,
                text_length=len(original),
                is_partial=is_partial,
                multiple_hits=len(matched),
            )

        slots = self._extract_slots(lowered)
        latency_ms = (time.perf_counter() - start) * 1000.0

        return ClassificationResult(
            intent=intent,
            confidence=confidence,
            slots=slots,
            language=language,
            matched_phrases=matched,
            normalized_text=normalized,
            original_text=original,
            latency_ms=latency_ms,
            is_partial=is_partial,
        )

    @staticmethod
    def _detect_language(text: str) -> str:
        sw_hits = sum(1 for marker in SWAHILI_MARKERS if marker in text)
        if sw_hits >= 2:
            return "sw"
        if sw_hits == 1:
            return "mixed"
        return "en"

    @staticmethod
    def _extract_slots(text: str) -> dict[str, str]:
        slots: dict[str, str] = {}
        for name, pattern in _SLOT_PATTERNS.items():
            match = pattern.search(text)
            if match:
                slots[name] = match.group(1) if match.lastindex else match.group(0)
        return slots
