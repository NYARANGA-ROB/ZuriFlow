"""Character n-gram embedding similarity matcher for fuzzy slang lookup."""

from __future__ import annotations

import math
import re
from collections import Counter

from api.services.kenyan_normalize.config import KenyanNormalizeConfig
from api.services.kenyan_normalize.dictionary.manager import SlangDictionaryManager
from api.services.kenyan_normalize.types import SimilarityMatch


class EmbeddingSimilarityMatcher:
    """Lightweight fuzzy matcher — no external embedding model required.

  Uses character n-gram cosine similarity against dictionary keys. Optionally
  upgrades to ``sentence-transformers`` when installed (see ``match_with_model``).
    """

    def __init__(self, config: KenyanNormalizeConfig, dictionary: SlangDictionaryManager) -> None:
        self._config = config
        self._dictionary = dictionary
        self._vector_cache: dict[str, dict[str, float]] = {}
        self._build_cache()

    def _build_cache(self) -> None:
        self._vector_cache.clear()
        for key in self._dictionary.all_token_keys():
            self._vector_cache[key] = self._char_ngram_vector(key)

    def refresh(self) -> None:
        self._build_cache()

    @staticmethod
    def _char_ngram_vector(text: str, n: int = 3) -> dict[str, float]:
        normalized = re.sub(r"\s+", "", text.lower())
        if len(normalized) < n:
            normalized = normalized.ljust(n, "_")
        counts = Counter(normalized[i : i + n] for i in range(len(normalized) - n + 1))
        total = sum(counts.values()) or 1
        return {k: v / total for k, v in counts.items()}

    @staticmethod
    def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in set(a) | set(b))
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def match_token(self, token: str) -> SimilarityMatch | None:
        """Find the best dictionary key for an unknown token."""
        if not token or len(token) < 2:
            return None

        query_vec = self._char_ngram_vector(token, self._config.ngram_size)
        scored: list[tuple[float, str]] = []
        for key, key_vec in self._vector_cache.items():
            score = self.cosine_similarity(query_vec, key_vec)
            if score >= self._config.similarity_threshold:
                scored.append((score, key))

        if not scored:
            return None

        scored.sort(reverse=True)
        best_score, best_key = scored[0]
        entry = self._dictionary.lookup_token(best_key)
        if entry is None:
            return None

        return SimilarityMatch(
            query=token,
            matched_key=best_key,
            target=entry.target,
            score=best_score,
        )

    def match_phrase(self, text: str) -> SimilarityMatch | None:
        """Fuzzy whole-phrase match against phrase sources."""
        lowered = text.strip().lower()
        if not lowered:
            return None

        query_vec = self._char_ngram_vector(lowered, self._config.ngram_size)
        best: SimilarityMatch | None = None
        for source, entry in self._dictionary._phrase_index:  # noqa: SLF001
            score = self.cosine_similarity(
                query_vec,
                self._char_ngram_vector(source, self._config.ngram_size),
            )
            if score < self._config.fuzzy_phrase_threshold:
                continue
            if best is None or score > best.score:
                best = SimilarityMatch(
                    query=lowered,
                    matched_key=source,
                    target=entry.target,
                    score=score,
                )
        return best

    def top_k(self, token: str, k: int | None = None) -> list[SimilarityMatch]:
        limit = k or self._config.similarity_top_k
        query_vec = self._char_ngram_vector(token, self._config.ngram_size)
        scored: list[tuple[float, str]] = []
        for key, key_vec in self._vector_cache.items():
            score = self.cosine_similarity(query_vec, key_vec)
            scored.append((score, key))
        scored.sort(reverse=True)
        results: list[SimilarityMatch] = []
        for score, key in scored[:limit]:
            entry = self._dictionary.lookup_token(key)
            if entry is None:
                continue
            results.append(
                SimilarityMatch(query=token, matched_key=key, target=entry.target, score=score)
            )
        return results
