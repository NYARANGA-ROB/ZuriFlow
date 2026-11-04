"""Core token and phrase normalization engine."""

from __future__ import annotations

from api.services.kenyan_normalize.config import KenyanNormalizeConfig
from api.services.kenyan_normalize.dictionary.manager import SlangDictionaryManager
from api.services.kenyan_normalize.embeddings import EmbeddingSimilarityMatcher
from api.services.kenyan_normalize.semantic import SemanticCorrectionLayer
from api.services.kenyan_normalize.types import (
    NormalizeResult,
    SimilarityMatch,
    TokenMapping,
    TokenSource,
)


class KenyanLanguageNormalizer:
    """Normalize Sheng / Swahili / code-switched utterances to structured English."""

    def __init__(
        self,
        config: KenyanNormalizeConfig,
        dictionary: SlangDictionaryManager,
        matcher: EmbeddingSimilarityMatcher,
        semantic: SemanticCorrectionLayer,
    ) -> None:
        self._config = config
        self._dictionary = dictionary
        self._matcher = matcher
        self._semantic = semantic

    def normalize(self, text: str) -> NormalizeResult:
        original = text.strip()
        if not original:
            return NormalizeResult(original="", normalized="")

        mappings: list[TokenMapping] = []
        similarity_matches: list[SimilarityMatch] = []
        intent: str | None = None

        # 1. Exact phrase match
        phrase = self._dictionary.lookup_phrase(original)
        if phrase is not None:
            return NormalizeResult(
                original=original,
                normalized=phrase.target,
                intent=phrase.intent,
                mappings=[
                    TokenMapping(
                        original=original,
                        normalized=phrase.target,
                        source=TokenSource.PHRASE,
                        confidence=1.0,
                    )
                ],
                metadata={"matched_phrase": phrase.source},
            )

        # 2. Fuzzy phrase match
        if self._config.enable_fuzzy_phrases:
            fuzzy = self._matcher.match_phrase(original)
            if fuzzy is not None:
                similarity_matches.append(fuzzy)
                return NormalizeResult(
                    original=original,
                    normalized=fuzzy.target,
                    mappings=[
                        TokenMapping(
                            original=original,
                            normalized=fuzzy.target,
                            source=TokenSource.PHRASE,
                            confidence=fuzzy.score,
                        )
                    ],
                    similarity_matches=similarity_matches,
                    metadata={"fuzzy_phrase": fuzzy.matched_key},
                )

        # 3. Token-by-token normalization (code-switch path)
        tokens = self._dictionary.tokenize(original)
        normalized_tokens: list[str] = []

        for token in tokens:
            entry = self._dictionary.lookup_token(token)
            if entry is not None:
                normalized_tokens.append(entry.target)
                mappings.append(
                    TokenMapping(
                        original=token,
                        normalized=entry.target,
                        source=TokenSource.DICTIONARY,
                        confidence=1.0,
                    )
                )
                continue

            # 4. Embedding similarity fallback
            match = self._matcher.match_token(token)
            if match is not None:
                normalized_tokens.append(match.target)
                similarity_matches.append(match)
                mappings.append(
                    TokenMapping(
                        original=token,
                        normalized=match.target,
                        source=TokenSource.EMBEDDING,
                        confidence=match.score,
                    )
                )
                continue

            normalized_tokens.append(token)
            mappings.append(
                TokenMapping(
                    original=token,
                    normalized=token,
                    source=TokenSource.ORIGINAL,
                    confidence=1.0,
                )
            )

        joined = " ".join(normalized_tokens)

        # Infer intent from partial phrase matches
        intent = self._infer_intent(original, tokens)

        # 5. Semantic correction (possessive reorder, intent templates)
        corrected, semantic_maps = self._semantic.correct(
            joined, intent=intent, existing_mappings=mappings
        )
        mappings.extend(semantic_maps)

        return NormalizeResult(
            original=original,
            normalized=corrected,
            intent=intent,
            mappings=mappings,
            similarity_matches=similarity_matches,
            metadata={"token_count": len(tokens)},
        )

    def _infer_intent(self, text: str, tokens: list[str]) -> str | None:
        lowered = text.lower()
        if any(w in tokens for w in ("balance", "salio")) or "balance" in lowered:
            if any(w in tokens for w in ("nataka", "want", "nipe", "give", "cheki", "check")):
                return "request_balance"
        if any(w in tokens for w in ("sasa", "mambo", "habari", "vipi")):
            return "greeting"
        if any(w in tokens for w in ("asante", "shukrani")):
            return "gratitude"
        if any(w in tokens for w in ("poa", "sawa")):
            return "acknowledgment"
        return None
