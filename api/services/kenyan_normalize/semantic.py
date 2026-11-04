"""Semantic correction layer — grammar, word order, intent preservation."""

from __future__ import annotations

import re

from api.services.kenyan_normalize.config import KenyanNormalizeConfig
from api.services.kenyan_normalize.types import TokenMapping, TokenSource


class SemanticCorrectionLayer:
    """Reorder and polish token-normalized text while preserving intent.

  Handles common Swahili-English code-switch patterns:
    - ``I want balance my``  -> ``I want my balance``
    - ``give me balance my`` -> ``give me my balance``
    - ``check balance my``   -> ``check my balance``
    """

    # possessive: <noun> my -> my <noun> (single-token noun only)
    _POSSESSIVE_MY = re.compile(
        r"\b(\w+)\s+my\b",
        re.IGNORECASE,
    )
    _POSSESSIVE_YOUR = re.compile(
        r"\b(\w+(?:\s+\w+)?)\s+your\b",
        re.IGNORECASE,
    )

    # Swahili infinitive fragments left after token map
    _TO_VERB = re.compile(r"\bI want to see\b", re.IGNORECASE)

    def __init__(self, config: KenyanNormalizeConfig) -> None:
        self._config = config

    def correct(
        self,
        text: str,
        *,
        intent: str | None = None,
        existing_mappings: list[TokenMapping] | None = None,
    ) -> tuple[str, list[TokenMapping]]:
        if not self._config.apply_semantic_correction:
            return text, []

        corrected = text.strip()
        extra: list[TokenMapping] = []

        before = corrected
        corrected = self._fix_possessive_my(corrected)
        if corrected != before:
            extra.append(
                TokenMapping(
                    original=before,
                    normalized=corrected,
                    source=TokenSource.SEMANTIC,
                    confidence=0.95,
                )
            )

        before = corrected
        corrected = self._fix_possessive_your(corrected)
        if corrected != before:
            extra.append(
                TokenMapping(
                    original=before,
                    normalized=corrected,
                    source=TokenSource.SEMANTIC,
                    confidence=0.95,
                )
            )

        before = corrected
        corrected = self._apply_intent_templates(corrected, intent)
        if corrected != before:
            extra.append(
                TokenMapping(
                    original=before,
                    normalized=corrected,
                    source=TokenSource.SEMANTIC,
                    confidence=0.9,
                )
            )

        before = corrected
        corrected = self._normalize_whitespace(corrected)
        corrected = self._capitalize_sentence(corrected, intent=intent, prior=existing_mappings)
        if corrected != before and not extra:
            extra.append(
                TokenMapping(
                    original=before,
                    normalized=corrected,
                    source=TokenSource.SEMANTIC,
                    confidence=0.8,
                )
            )

        return corrected, extra

    def _fix_possessive_my(self, text: str) -> str:
        def repl(match: re.Match) -> str:
            noun = match.group(1).strip()
            if noun.lower() in {"my", "i", "want", "give", "me", "to", "see", "check"}:
                return match.group(0)
            return f"my {noun}"

        return self._POSSESSIVE_MY.sub(repl, text)

    def _fix_possessive_your(self, text: str) -> str:
        def repl(match: re.Match) -> str:
            noun = match.group(1).strip()
            return f"your {noun}"

        return self._POSSESSIVE_YOUR.sub(repl, text)

    def _apply_intent_templates(self, text: str, intent: str | None) -> str:
        lowered = text.lower().strip()
        if intent == "request_balance":
            if lowered == "i want balance":
                return "I want my balance"
            if lowered == "give me balance":
                return "give me my balance"
            if lowered == "check balance":
                return "check my balance"
        if intent == "greeting" and self._config.preserve_greeting_tone:
            if lowered in {"hello", "hello boss", "how are you"}:
                return lowered
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _capitalize_sentence(
        text: str,
        *,
        intent: str | None,
        prior: list[TokenMapping] | None,
    ) -> str:
        if not text or intent is None:
            return text
        # Preserve casual greeting tone — don't force title case on "hello boss"
        if intent == "greeting":
            return text[0].lower() + text[1:] if len(text) > 1 else text.lower()
        return text[0].upper() + text[1:] if text else text
