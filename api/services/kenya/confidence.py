"""Confidence gates for Kenyan conversational intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from api.services.kenya.config import KenyaLanguage
from api.services.kenyan_intent.types import BusinessIntent

INTENT_PROCEED = 0.62
INTENT_FINANCIAL = 0.78
LANGUAGE_LOW = 0.42
CLARIFY = 0.55

_FINANCIAL = {BusinessIntent.PAYMENT}

_CLARIFY = {
    KenyaLanguage.ENGLISH: "Sorry, I did not catch that. Could you say it another way?",
    KenyaLanguage.KISWAHILI: "Samahani, sikuelewa vizuri. Unaweza kurudia tafadhali?",
    KenyaLanguage.SHENG: "Sawa, sikuskia vizuri. Unaweza repeat?",
    KenyaLanguage.MIXED: "Sawa, sikuelewa vizuri — unaweza repeat?",
}


@dataclass(frozen=True)
class ConfidenceDecision:
    overall: float
    language: float
    intent: float
    action: str  # proceed | clarify | block_financial
    allow_financial: bool
    allow_transfer: bool
    clarification_prompt: str | None
    reason: str

    def to_dict(self) -> dict:
        return {
            "overall": round(self.overall, 4),
            "language": round(self.language, 4),
            "intent": round(self.intent, 4),
            "action": self.action,
            "allow_financial": self.allow_financial,
            "allow_transfer": self.allow_transfer,
            "clarification_prompt": self.clarification_prompt,
            "reason": self.reason,
        }


def decide_confidence(
    *,
    language_confidence: float,
    intent_confidence: float,
    intent: BusinessIntent | None,
    reply_language: KenyaLanguage,
) -> ConfidenceDecision:
    intent_c = intent_confidence if intent and intent != BusinessIntent.UNKNOWN else 0.0
    overall = min(language_confidence or 0.0, intent_c or language_confidence or 0.0)
    if intent_c == 0.0:
        overall = language_confidence * 0.5

    financial = intent in _FINANCIAL
    if language_confidence < LANGUAGE_LOW or (intent_c and intent_c < CLARIFY and not financial):
        return ConfidenceDecision(
            overall=overall,
            language=language_confidence,
            intent=intent_c,
            action="clarify",
            allow_financial=False,
            allow_transfer=False,
            clarification_prompt=_CLARIFY.get(reply_language, _CLARIFY[KenyaLanguage.MIXED]),
            reason="low_confidence",
        )

    if financial and intent_c < INTENT_FINANCIAL:
        return ConfidenceDecision(
            overall=overall,
            language=language_confidence,
            intent=intent_c,
            action="block_financial",
            allow_financial=False,
            allow_transfer=False,
            clarification_prompt=(
                "Before I send any payment, please confirm the amount in shillings."
                if reply_language == KenyaLanguage.ENGLISH
                else "Kabla sija-send malipo, confirm kiasi kwa shilingi."
            ),
            reason="financial_needs_confirmation",
        )

    if intent_c and intent_c < INTENT_PROCEED:
        return ConfidenceDecision(
            overall=overall,
            language=language_confidence,
            intent=intent_c,
            action="clarify",
            allow_financial=False,
            allow_transfer=intent == BusinessIntent.ESCALATION and intent_c >= 0.7,
            clarification_prompt=_CLARIFY.get(reply_language, _CLARIFY[KenyaLanguage.MIXED]),
            reason="intent_uncertain",
        )

    return ConfidenceDecision(
        overall=max(overall, intent_c, language_confidence),
        language=language_confidence,
        intent=intent_c,
        action="proceed",
        allow_financial=financial and intent_c >= INTENT_FINANCIAL,
        allow_transfer=True,
        clarification_prompt=None,
        reason="ok",
    )
