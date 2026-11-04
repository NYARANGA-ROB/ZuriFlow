"""Configuration for Kenyan language normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from api.constants import (
    APP_ROOT_DIR,
    KENYAN_NORMALIZE_DICTIONARY_PATH,
    KENYAN_NORMALIZE_ENABLED,
)


@dataclass(frozen=True)
class KenyanNormalizeConfig:
    enabled: bool = KENYAN_NORMALIZE_ENABLED
    dictionary_path: Path = Path(
        KENYAN_NORMALIZE_DICTIONARY_PATH
        or (APP_ROOT_DIR / "data" / "kenyan_normalize" / "dictionary.json")
    )

    # Embedding similarity matcher
    similarity_threshold: float = 0.72
    similarity_top_k: int = 3
    ngram_size: int = 3

    # Semantic correction
    apply_semantic_correction: bool = True
    preserve_greeting_tone: bool = True

    # Fuzzy phrase matching
    enable_fuzzy_phrases: bool = True
    fuzzy_phrase_threshold: float = 0.85


DEFAULT_KENYAN_NORMALIZE_CONFIG = KenyanNormalizeConfig()
