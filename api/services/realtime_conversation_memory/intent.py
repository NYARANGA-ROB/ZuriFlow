"""Caller intent tracking for voice conversations."""

from __future__ import annotations

import re

from api.services.realtime_conversation_memory.config import RealtimeMemoryConfig
from api.services.realtime_conversation_memory.types import CallIntent, IntentState

_INTENT_RULES: list[tuple[CallIntent, list[str], float]] = [
    (CallIntent.GREETING, ["hello", "hi", "habari", "mambo", "sasa", "good morning"], 0.85),
    (CallIntent.REQUEST_BALANCE, ["balance", "salio", "account balance", "how much"], 0.9),
    (CallIntent.REQUEST_PAYMENT, ["pay", "lipa", "payment", "send money", "mpesa"], 0.88),
    (CallIntent.REQUEST_SUPPORT, ["help", "problem", "issue", "support", "saidia"], 0.85),
    (CallIntent.ACCOUNT_INQUIRY, ["account", "akaunti", "number", "details"], 0.8),
    (CallIntent.CONFIRMATION, ["yes", "ndio", "sawa", "okay", "confirm"], 0.75),
    (CallIntent.GRATITUDE, ["thank", "asante", "shukrani"], 0.8),
    (CallIntent.FAREWELL, ["bye", "goodbye", "kwaheri", "talk later"], 0.85),
]

_SLOT_PATTERNS = {
    "amount": re.compile(r"\b(\d[\d,]*)\s*(?:ksh|shillings?|bob)?\b", re.I),
    "phone": re.compile(r"\b(?:\+?254|0)?7\d{8}\b"),
    "account_ref": re.compile(r"\b(?:account|acc(?:ount)?)\s*(?:number|no\.?)?\s*[:#]?\s*(\w+)\b", re.I),
}


class IntentTracker:
    """Track and update caller intent with lightweight rule matching."""

    def __init__(self, config: RealtimeMemoryConfig) -> None:
        self._config = config

    def update(self, text: str, prior: IntentState | None = None) -> IntentState:
        state = prior or IntentState()
        lowered = text.lower().strip()
        if not lowered:
            return state

        best_intent = CallIntent.UNKNOWN
        best_score = 0.0
        for intent, keywords, base_conf in _INTENT_RULES:
            for kw in keywords:
                if kw in lowered:
                    score = base_conf + min(0.1, len(kw) / 50.0)
                    if score > best_score:
                        best_score = score
                        best_intent = intent

        if best_intent == CallIntent.UNKNOWN and state.current != CallIntent.UNKNOWN:
            best_intent = state.current
            best_score = max(0.0, state.confidence - self._config.intent_confidence_decay)

        if best_intent != state.current and best_intent != CallIntent.UNKNOWN:
            state.history.append(state.current)
            state.current = best_intent
            state.confidence = best_score
        elif best_intent != CallIntent.UNKNOWN:
            state.confidence = min(1.0, max(state.confidence, best_score))

        slots = self._extract_slots(lowered)
        state.slots.update({k: v for k, v in slots.items() if v})
        return state

    def mark_interruption(self, state: IntentState) -> IntentState:
        state.history.append(state.current)
        state.current = CallIntent.INTERRUPTION
        state.confidence = 0.95
        return state

    def _extract_slots(self, text: str) -> dict[str, str]:
        slots: dict[str, str] = {}
        amount = _SLOT_PATTERNS["amount"].search(text)
        if amount:
            slots["amount"] = amount.group(1).replace(",", "")
        phone = _SLOT_PATTERNS["phone"].search(text)
        if phone:
            slots["phone"] = phone.group(0)
        acct = _SLOT_PATTERNS["account_ref"].search(text)
        if acct:
            slots["account_ref"] = acct.group(1)
        return slots
