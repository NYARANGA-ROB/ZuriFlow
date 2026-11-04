from __future__ import annotations

from dataclasses import dataclass

from api.constants import KENYAN_INTENT_ENABLED, KENYAN_NORMALIZE_ENABLED


@dataclass(frozen=True)
class KenyanIntentConfig:
    enabled: bool = KENYAN_INTENT_ENABLED
    use_normalization: bool = KENYAN_NORMALIZE_ENABLED
    partial_confidence_threshold: float = 0.82
    final_confidence_threshold: float = 0.55
    route_confidence_threshold: float = 0.6
    intent_confidence_decay: float = 0.12
    max_history: int = 8
    commit_on_partial: bool = False


DEFAULT_KENYAN_INTENT_CONFIG = KenyanIntentConfig()
