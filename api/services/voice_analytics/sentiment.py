from __future__ import annotations

import re

from api.services.voice_analytics.types import SentimentLabel

_POSITIVE = frozenset(
    {
        "thank",
        "thanks",
        "asante",
        "good",
        "great",
        "perfect",
        "sawa",
        "nzuri",
        "helpful",
        "excellent",
        "appreciate",
    }
)
_NEGATIVE = frozenset(
    {
        "angry",
        "bad",
        "terrible",
        "hate",
        "useless",
        "shida",
        "problem",
        "complaint",
        "worst",
        "frustrated",
        "hapana",
        "sijapenda",
        "bure",
    }
)
_NEGATORS = frozenset({"not", "no", "never", "hapana", "sio"})


def score_sentiment(text: str) -> tuple[SentimentLabel, float]:
    """Lightweight lexicon sentiment for realtime voice transcripts."""
    lowered = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in lowered.split() if t]
    if not tokens:
        return SentimentLabel.NEUTRAL, 0.5

    score = 0.0
    for i, token in enumerate(tokens):
        negated = i > 0 and tokens[i - 1] in _NEGATORS
        if token in _POSITIVE:
            score += -0.35 if negated else 0.35
        elif token in _NEGATIVE:
            score += 0.35 if negated else -0.35

    if score > 0.15:
        label = SentimentLabel.POSITIVE
    elif score < -0.15:
        label = SentimentLabel.NEGATIVE
    else:
        label = SentimentLabel.NEUTRAL

    confidence = min(1.0, max(0.0, 0.5 + abs(score)))
    return label, round(confidence, 4)
