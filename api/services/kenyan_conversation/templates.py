"""Multilingual prompt templates for Kenyan voice agents."""

from __future__ import annotations

from api.services.kenyan_conversation.types import LanguageMode

CONFIRMATIONS_EN = [
    "Sure thing.",
    "Got it.",
    "Okay, one moment.",
    "Alright.",
    "No problem.",
]

CONFIRMATIONS_SW = [
    "Sawa.",
    "Poa.",
    "Sawa boss.",
    "Sawa, nangoja kidogo.",
]

CONFIRMATIONS_MIXED = [
    "Sawa, got it.",
    "Poa, one moment.",
    "Alright, sawa.",
    "Sure, niko hapa.",
]

GREETINGS_EN = [
    "Hello, how can I help?",
    "Hi there, what can I do for you?",
]

GREETINGS_SW = [
    "Habari, naweza kukusaidia vipi?",
    "Mambo, nikusaidie nini leo?",
]

GREETINGS_MIXED = [
    "Mambo, how can I help today?",
    "Habari, what can I do for you?",
]

CLOSINGS_EN = [
    "Anything else I can help with?",
    "Let me know if you need anything else.",
]

CLOSINGS_SW = [
    "Kuna kingine naweza kusaidia?",
    "Niambie kama unahitaji msaada zaidi.",
]

CLOSINGS_MIXED = [
    "Sawa, anything else?",
    "Poa — need help with anything else?",
]

ACKNOWLEDGMENTS_EN = [
    "I hear you.",
    "Understood.",
]

ACKNOWLEDGMENTS_SW = [
    "Naelewa.",
    "Sawa, nimekusikia.",
]

ACKNOWLEDGMENTS_MIXED = [
    "Sawa, I hear you.",
    "Naelewa — got it.",
]

MULTILINGUAL_STYLE_BLOCK = {
    LanguageMode.ENGLISH: (
        "Respond in clear Kenyan English. Keep it conversational, not formal."
    ),
    LanguageMode.SWAHILI: (
        "Respond in natural Swahili suited for Kenyan phone calls. "
        "Use simple, direct sentences."
    ),
    LanguageMode.MIXED: (
        "You may mix Kenyan English and Swahili naturally, as people do on phone calls. "
        "Do not force Swahili into every sentence — use it where it sounds natural "
        "(greetings, confirmations, empathy). English carries the factual content."
    ),
}


def confirmations(mode: LanguageMode) -> list[str]:
    return {
        LanguageMode.ENGLISH: CONFIRMATIONS_EN,
        LanguageMode.SWAHILI: CONFIRMATIONS_SW,
        LanguageMode.MIXED: CONFIRMATIONS_MIXED,
    }[mode]


def greetings(mode: LanguageMode) -> list[str]:
    return {
        LanguageMode.ENGLISH: GREETINGS_EN,
        LanguageMode.SWAHILI: GREETINGS_SW,
        LanguageMode.MIXED: GREETINGS_MIXED,
    }[mode]


def closings(mode: LanguageMode) -> list[str]:
    return {
        LanguageMode.ENGLISH: CLOSINGS_EN,
        LanguageMode.SWAHILI: CLOSINGS_SW,
        LanguageMode.MIXED: CLOSINGS_MIXED,
    }[mode]


def acknowledgments(mode: LanguageMode) -> list[str]:
    return {
        LanguageMode.ENGLISH: ACKNOWLEDGMENTS_EN,
        LanguageMode.SWAHILI: ACKNOWLEDGMENTS_SW,
        LanguageMode.MIXED: ACKNOWLEDGMENTS_MIXED,
    }[mode]
