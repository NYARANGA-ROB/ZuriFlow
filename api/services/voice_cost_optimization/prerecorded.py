"""Prerecorded response library for zero-LLM turns."""

from __future__ import annotations

import re
from typing import Any

# Keys map to locale-specific phrases played without LLM generation.
PRERECORDED_LIBRARY: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "Hello, thank you for taking my call. How can I help you today?",
        "sw": "Habari, asante kwa kupokea simu yangu. Naweza kukusaidia vipi leo?",
        "mixed": "Hello, habari — thank you for taking my call. How can I help you today?",
    },
    "please_hold": {
        "en": "One moment please while I check that for you.",
        "sw": "Subiri kidogo nikihakikisha hilo kwako.",
        "mixed": "One moment please — subiri kidogo nikihakikisha hilo.",
    },
    "did_not_catch": {
        "en": "Sorry, I did not catch that. Could you please repeat?",
        "sw": "Samahani, sikusikia vizuri. Tafadhali rudia?",
        "mixed": "Sorry, sikusikia vizuri — could you please repeat?",
    },
    "goodbye": {
        "en": "Thank you for your time. Have a good day.",
        "sw": "Asante kwa muda wako. Siku njema.",
        "mixed": "Asante for your time. Have a good day.",
    },
    "thank_you": {
        "en": "Thank you, I appreciate that.",
        "sw": "Asante sana, ninashukuru.",
        "mixed": "Asante sana — thank you, I appreciate that.",
    },
    "confirm_yes": {
        "en": "Great, I have noted that.",
        "sw": "Sawa, nimeandika hilo.",
        "mixed": "Sawa — great, I have noted that.",
    },
    "payment_received": {
        "en": "Thank you, your payment has been received.",
        "sw": "Asante, malipo yako yamepokelewa.",
        "mixed": "Asante — your payment has been received.",
    },
}

# User utterance patterns → prerecorded key.
_UTTERANCE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(hi|hello|hey|habari|mambo)\b", re.I), "greeting"),
    (re.compile(r"\b(bye|goodbye|kwaheri|nimekwisha)\b", re.I), "goodbye"),
    (re.compile(r"\b(thank you|thanks|asante)\b", re.I), "thank_you"),
    (re.compile(r"\b(yes|yeah|sawa|ndio)\b", re.I), "confirm_yes"),
    (re.compile(r"\b(hold on|one moment|subiri)\b", re.I), "please_hold"),
)

# Kenyan intent values → prerecorded key.
_INTENT_MAP: dict[str, str] = {
    "greeting": "greeting",
    "goodbye": "goodbye",
    "thanks": "thank_you",
    "payment_confirmed": "payment_received",
}


def prerecorded_for_intent(intent: str, *, locale: str = "mixed") -> str | None:
    key = _INTENT_MAP.get(intent)
    if not key:
        return None
    return prerecorded_text(key, locale=locale)


def prerecorded_text(key: str, *, locale: str = "mixed") -> str | None:
    entry = PRERECORDED_LIBRARY.get(key)
    if not entry:
        return None
    return entry.get(locale) or entry.get("mixed") or entry.get("en")


def match_prerecorded(user_text: str, *, locale: str = "mixed") -> tuple[str, str] | None:
    """Return (key, text) if user utterance maps to a prerecorded response."""
    text = user_text.strip()
    if not text:
        return None
    if len(text) <= 40:
        for pattern, key in _UTTERANCE_PATTERNS:
            if pattern.search(text):
                phrase = prerecorded_text(key, locale=locale)
                if phrase:
                    return key, phrase
    return None


def list_prerecorded_keys() -> list[dict[str, Any]]:
    return [
        {"key": key, "locales": list(phrases.keys())}
        for key, phrases in PRERECORDED_LIBRARY.items()
    ]
