from __future__ import annotations

import re

_CONSENT_PHRASES = (
    "yes",
    "yeah",
    "yep",
    "ndio",
    "sawa",
    "okay",
    "ok",
    "sure",
    "go ahead",
    "lipa",
    "pay",
    "proceed",
    "endesha",
    "tuma",
)

_DECLINE_PHRASES = (
    "no",
    "nah",
    "hapana",
    "not now",
    "later",
    "cancel",
    "stop",
    "sitaki",
)

_RETRY_PHRASES = (
    "try again",
    "retry",
    "jaribu tena",
    "repeat",
)

_STATUS_PHRASES = (
    "did it work",
    "payment status",
    "imefika",
    "received",
    "receipt",
    "malipo",
)


class VoicePaymentConfirmation:
    """Detect consent and craft spoken payment prompts."""

    def is_consent(self, text: str) -> bool:
        lowered = text.lower().strip()
        return any(p in lowered for p in _CONSENT_PHRASES)

    def is_decline(self, text: str) -> bool:
        lowered = text.lower().strip()
        return any(p in lowered for p in _DECLINE_PHRASES)

    def wants_retry(self, text: str) -> bool:
        lowered = text.lower().strip()
        return any(p in lowered for p in _RETRY_PHRASES)

    def asks_payment_status(self, text: str) -> bool:
        lowered = text.lower().strip()
        return any(p in lowered for p in _STATUS_PHRASES)

    def offer_prompt(self, *, amount: float, currency: str, language: str) -> str:
        if language == "sw":
            return (
                f"Ungependa kulipa {currency} {amount:g} kupitia M-Pesa sasa? "
                "Sema ndio ili nitume ombi la malipo kwenye simu yako."
            )
        if language == "mixed":
            return (
                f"Would you like to pay {currency} {amount:g} via M-Pesa now? "
                "Sema ndio / say yes and I'll send the STK push to your phone."
            )
        return (
            f"Would you like to pay {currency} {amount:g} via M-Pesa now? "
            "Say yes and I'll send a payment request to your phone."
        )

    def stk_sent_prompt(self, *, language: str) -> str:
        if language == "sw":
            return "Nimetuma ombi la malipo kwenye simu yako. Tafadhali ingiza PIN yako ya M-Pesa."
        if language == "mixed":
            return (
                "I've sent the payment request to your phone. "
                "Please enter your M-Pesa PIN / ingiza PIN yako."
            )
        return "I've sent a payment request to your phone. Please enter your M-Pesa PIN."

    def success_prompt(
        self,
        *,
        amount: float,
        currency: str,
        receipt: str | None,
        language: str,
    ) -> str:
        receipt_part = receipt or "confirmed"
        if language == "sw":
            return (
                f"Malipo ya {currency} {amount:g} yamefanikiwa. "
                f"Namba ya risiti ni {receipt_part}."
            )
        if language == "mixed":
            return (
                f"Payment of {currency} {amount:g} received. "
                f"Receipt / risiti number is {receipt_part}."
            )
        return f"Payment of {currency} {amount:g} received. Your receipt number is {receipt_part}."

    def failed_prompt(self, *, language: str, can_retry: bool) -> str:
        if language == "sw":
            base = "Malipo hayakufanikiwa."
            return f"{base} Sema jaribu tena ikiwa ungependa kurudia." if can_retry else base
        if language == "mixed":
            base = "The payment didn't go through."
            return f"{base} Say try again / jaribu tena if you'd like to retry." if can_retry else base
        base = "The payment didn't go through."
        return f"{base} Say try again if you'd like me to resend the request." if can_retry else base

    def cancelled_prompt(self, *, language: str) -> str:
        if language == "sw":
            return "Ulighairi ombi la malipo. Niambie ukipenda kujaribu tena."
        if language == "mixed":
            return "Payment was cancelled. Let me know / niambie if you want to try again."
        return "Payment was cancelled. Let me know if you'd like to try again."

    def system_hint(self, *, state: str, amount: float, currency: str) -> str:
        return (
            f"[Voice M-Pesa] Payment workflow active — state={state}, "
            f"amount={currency} {amount:g}. "
            "Guide the caller through M-Pesa payment. Wait for explicit consent before paying."
        )

    def parse_amount_from_text(self, text: str) -> float | None:
        match = re.search(r"\b(\d[\d,]*)\s*(?:ksh|kes|shillings?|bob)?\b", text, re.I)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
