"""Load continuously learned intent patterns."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from loguru import logger

from api.constants import KENYAN_CL_DATA_PATH
from api.services.kenyan_intent.patterns import INTENT_PATTERNS, IntentPattern
from api.services.kenyan_intent.types import BusinessIntent

_LEARNED_FILE = Path(__file__).resolve().parents[2] / "data" / "kenyan_intent" / "learned_patterns.json"


@lru_cache(maxsize=1)
def load_learned_intent_patterns() -> dict[BusinessIntent, tuple[IntentPattern, ...]]:
    paths = [_LEARNED_FILE]
    cl_root = Path(KENYAN_CL_DATA_PATH)
    if cl_root.exists():
        paths.extend(cl_root.glob("org_*/intent_learned_patterns.json"))

    merged: dict[BusinessIntent, list[IntentPattern]] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("skip learned intent file {}: {}", path, e)
            continue
        for item in data.get("patterns") or []:
            intent_name = item.get("intent")
            phrase = item.get("phrase")
            if not intent_name or not phrase:
                continue
            try:
                intent = BusinessIntent(intent_name)
            except ValueError:
                continue
            merged.setdefault(intent, []).append(
                IntentPattern(
                    phrase=str(phrase).lower(),
                    weight=float(item.get("weight", 0.75)),
                    language=item.get("language", "mixed"),
                )
            )
    return {k: tuple(v) for k, v in merged.items()}


def merged_intent_patterns() -> dict[BusinessIntent, tuple[IntentPattern, ...]]:
    learned = load_learned_intent_patterns()
    out: dict[BusinessIntent, list[IntentPattern]] = {
        intent: list(patterns) for intent, patterns in INTENT_PATTERNS.items()
    }
    for intent, patterns in learned.items():
        out.setdefault(intent, []).extend(patterns)
    return {k: tuple(v) for k, v in out.items()}


def invalidate_learned_pattern_cache() -> None:
    load_learned_intent_patterns.cache_clear()
