"""Types for Kenyan language normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenSource(str, Enum):
    ORIGINAL = "original"
    DICTIONARY = "dictionary"
    PHRASE = "phrase"
    EMBEDDING = "embedding"
    SEMANTIC = "semantic"


@dataclass(frozen=True)
class TokenMapping:
    original: str
    normalized: str
    source: TokenSource
    confidence: float = 1.0


@dataclass(frozen=True)
class SimilarityMatch:
    query: str
    matched_key: str
    target: str
    score: float


@dataclass
class NormalizeResult:
    """Output of the normalization pipeline."""

    original: str
    normalized: str
    intent: str | None = None
    mappings: list[TokenMapping] = field(default_factory=list)
    similarity_matches: list[SimilarityMatch] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "normalized": self.normalized,
            "intent": self.intent,
            "mappings": [
                {
                    "original": m.original,
                    "normalized": m.normalized,
                    "source": m.source.value,
                    "confidence": round(m.confidence, 4),
                }
                for m in self.mappings
            ],
            "similarity_matches": [
                {
                    "query": s.query,
                    "matched_key": s.matched_key,
                    "target": s.target,
                    "score": round(s.score, 4),
                }
                for s in self.similarity_matches
            ],
            "metadata": self.metadata,
        }
