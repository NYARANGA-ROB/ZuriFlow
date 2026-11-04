"""Workflow-selectable Kenyan conversation styles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KenyaConversationStyle(str, Enum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CASUAL_KENYAN = "casual_kenyan"
    SHENG_FRIENDLY = "sheng_friendly"
    KISWAHILI_FIRST = "kiswahili_first"
    ENGLISH_FIRST = "english_first"
    CORPORATE = "corporate"
    YOUTH_ORIENTED = "youth_oriented"
    CUSTOMER_CARE = "customer_care"


@dataclass(frozen=True)
class StyleProfile:
    style: KenyaConversationStyle
    label: str
    follow_caller_language: bool
    preferred_reply_language: str
    prompt_overlay: str
    allow_sheng: bool


_STYLES: dict[KenyaConversationStyle, StyleProfile] = {
    KenyaConversationStyle.PROFESSIONAL: StyleProfile(
        KenyaConversationStyle.PROFESSIONAL,
        "Professional",
        True,
        "en",
        "Speak clearly and respectfully. Light 'sawa' is fine. Avoid slang.",
        False,
    ),
    KenyaConversationStyle.FRIENDLY: StyleProfile(
        KenyaConversationStyle.FRIENDLY,
        "Friendly",
        True,
        "mixed",
        "Warm Kenyan hospitality. Short sentences. Match the caller's language.",
        False,
    ),
    KenyaConversationStyle.CASUAL_KENYAN: StyleProfile(
        KenyaConversationStyle.CASUAL_KENYAN,
        "Casual Kenyan",
        True,
        "mixed",
        "Sound like a helpful Kenyan on a phone call. Natural code-switching is OK.",
        True,
    ),
    KenyaConversationStyle.SHENG_FRIENDLY: StyleProfile(
        KenyaConversationStyle.SHENG_FRIENDLY,
        "Sheng-friendly",
        True,
        "sheng",
        "If the caller uses Sheng, you may reply with light Sheng. Keep amounts in plain numbers.",
        True,
    ),
    KenyaConversationStyle.KISWAHILI_FIRST: StyleProfile(
        KenyaConversationStyle.KISWAHILI_FIRST,
        "Kiswahili-first",
        False,
        "sw",
        "Reply in Kiswahili unless the caller clearly prefers English. Keep numbers clear.",
        False,
    ),
    KenyaConversationStyle.ENGLISH_FIRST: StyleProfile(
        KenyaConversationStyle.ENGLISH_FIRST,
        "English-first",
        False,
        "en",
        "Reply in English unless the caller clearly prefers Kiswahili.",
        False,
    ),
    KenyaConversationStyle.CORPORATE: StyleProfile(
        KenyaConversationStyle.CORPORATE,
        "Corporate",
        False,
        "en",
        "Formal corporate Kenyan English. No slang. Confirm before any payment.",
        False,
    ),
    KenyaConversationStyle.YOUTH_ORIENTED: StyleProfile(
        KenyaConversationStyle.YOUTH_ORIENTED,
        "Youth-oriented",
        True,
        "mixed",
        "Relaxed, brief, and current. Sheng is OK. Never mock the caller.",
        True,
    ),
    KenyaConversationStyle.CUSTOMER_CARE: StyleProfile(
        KenyaConversationStyle.CUSTOMER_CARE,
        "Customer-care",
        True,
        "mixed",
        "Empathetic support agent. Acknowledge first, then solve. Offer a human if stuck.",
        False,
    ),
}


def get_style(value: str | KenyaConversationStyle | None) -> StyleProfile:
    if isinstance(value, KenyaConversationStyle):
        return _STYLES[value]
    raw = (value or KenyaConversationStyle.CUSTOMER_CARE.value).lower()
    try:
        return _STYLES[KenyaConversationStyle(raw)]
    except ValueError:
        return _STYLES[KenyaConversationStyle.CUSTOMER_CARE]


def list_styles() -> list[dict]:
    return [
        {
            "id": p.style.value,
            "label": p.label,
            "follow_caller_language": p.follow_caller_language,
            "preferred_reply_language": p.preferred_reply_language,
            "prompt_overlay": p.prompt_overlay,
            "allow_sheng": p.allow_sheng,
        }
        for p in _STYLES.values()
    ]
