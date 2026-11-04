"""Conversational onboarding extraction. Never auto-publishes."""

from __future__ import annotations

import re
from typing import Any

from api.services.business_twin.extractors import wrap_untrusted

_QUESTIONS = (
    "What does your business do?",
    "Where are you located?",
    "What services do you provide?",
    "What are your opening hours?",
    "What are your prices?",
    "What questions do customers ask most often?",
    "Do customers make appointments?",
    "Do you accept M-Pesa?",
    "How should difficult customers be escalated?",
    "What languages should the agent use?",
)


def next_question(turn_index: int) -> str | None:
    if turn_index < 0 or turn_index >= len(_QUESTIONS):
        return None
    return _QUESTIONS[turn_index]


def extract_from_conversation(transcript: str) -> dict[str, Any]:
    text = transcript or ""
    lowered = text.lower()
    hours = re.findall(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", text, flags=re.I)
    mpesa = any(token in lowered for token in ("mpesa", "m-pesa", "till", "paybill"))
    languages: list[str] = []
    if "swahili" in lowered or "kiswahili" in lowered:
        languages.append("sw")
    if "sheng" in lowered:
        languages.append("sheng")
    if "english" in lowered:
        languages.append("en")
    if "mix" in lowered:
        languages.append("mixed")
    appointments = any(token in lowered for token in ("appointment", "book", "booking"))
    return {
        "description": text[:500],
        "hours_mentions": hours[:4],
        "mpesa": mpesa,
        "languages": languages or ["mixed"],
        "appointments": appointments,
        "confidence": 0.7,
        "status": "pending_review",
        "source_type": "AI_extraction",
        "untrusted_wrap": wrap_untrusted(text[:2000]),
        "questions": list(_QUESTIONS),
    }
