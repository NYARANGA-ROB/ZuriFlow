"""Conversation filters — sanitize agent responses before delivery."""

from __future__ import annotations

import re

from api.services.debt_collection.compliance.types import (
    ComplianceViolation,
    ComplianceViolationType,
    ViolationSeverity,
)

_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(pay now or else|final warning|last chance|no excuses|you have no choice)\b",
            re.IGNORECASE,
        ),
        "let's find a payment option that works for you",
    ),
    (
        re.compile(
            r"\b(must pay today|pay immediately or|non.?negotiable|we will not wait)\b",
            re.IGNORECASE,
        ),
        "we can discuss a realistic repayment plan",
    ),
    (
        re.compile(
            r"\b(arrest you|go to jail|send police|police will come)\b",
            re.IGNORECASE,
        ),
        "we prefer to resolve this cooperatively",
    ),
    (
        re.compile(
            r"\b(seize your (house|property|assets|car)|auction your)\b",
            re.IGNORECASE,
        ),
        "let's agree on a voluntary repayment arrangement",
    ),
    (
        re.compile(
            r"\b(blacklist you forever|ruin your credit forever|publish your name|name and shame)\b",
            re.IGNORECASE,
        ),
        "we want to help you clear this account fairly",
    ),
    (
        re.compile(
            r"\b(call you every day|call your boss|call your family|won't stop calling|harass)\b",
            re.IGNORECASE,
        ),
        "we will contact you only at reasonable times",
    ),
    (
        re.compile(
            r"\b(stupid|idiot|lazy|deadbeat|thief|conman|fraud|shut up)\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\b(lipa sasa au|onyo la mwisho|hakuna chaguo)\b",
            re.IGNORECASE,
        ),
        "tunaweza kupanga malipo yanayokufaa",
    ),
)

SAFE_FALLBACK: dict[str, str] = {
    "en": (
        "I apologise if that came across strongly. We want to work with you respectfully "
        "on a realistic repayment plan. Would a structured installment option help?"
    ),
    "sw": (
        "Samahani kama nilionekana kuwa mkali. Tunataka kufanya kazi nawe kwa heshima "
        "kupanga malipo yanayokufaa. Je, mpango wa awamu unaweza kusaidia?"
    ),
    "mixed": (
        "I apologise — we want to resolve this politely. We can offer a flexible payment "
        "plan or partial settlement. What amount could work for you this month?"
    ),
}


class ConversationFilters:
    """Replace or block non-compliant agent phrases."""

    def sanitize_agent_text(
        self,
        text: str,
        violations: list[ComplianceViolation],
        *,
        locale: str = "mixed",
    ) -> tuple[str, bool, bool]:
        """Return (filtered_text, was_modified, used_fallback)."""
        if not violations:
            return text, False, False

        blocking = [
            v
            for v in violations
            if v.severity in (ViolationSeverity.BLOCK, ViolationSeverity.CRITICAL)
        ]
        if not blocking:
            return self._append_polite_offer(text, locale), True, False

        filtered = text
        modified = False
        for pattern, replacement in _REPLACEMENTS:
            new_text, count = pattern.subn(replacement, filtered)
            if count:
                filtered = new_text
                modified = True

        filtered = re.sub(r"\s{2,}", " ", filtered).strip()
        filtered = re.sub(r"\s+([,.])", r"\1", filtered)

        still_blocked = any(
            v.violation_type
            in (
                ComplianceViolationType.ILLEGAL_THREAT,
                ComplianceViolationType.ABUSIVE_LANGUAGE,
                ComplianceViolationType.HARASSMENT,
            )
            for v in blocking
        )
        if still_blocked and self._needs_fallback(filtered, blocking):
            return SAFE_FALLBACK.get(locale, SAFE_FALLBACK["mixed"]), True, True

        if not self._has_polite_alternative(filtered):
            filtered = self._append_polite_offer(filtered, locale)
            modified = True

        return filtered, modified, False

    def _needs_fallback(
        self, text: str, violations: list[ComplianceViolation]
    ) -> bool:
        from api.services.debt_collection.compliance.rules import (
            AGENT_ABUSIVE,
            AGENT_HARASSMENT,
            AGENT_ILLEGAL_THREAT,
        )

        if AGENT_ILLEGAL_THREAT.search(text):
            return True
        if AGENT_ABUSIVE.search(text):
            return True
        if AGENT_HARASSMENT.search(text):
            return True
        return any(
            v.violation_type == ComplianceViolationType.AGGRESSIVE_NEGOTIATION
            for v in violations
        )

    def _has_polite_alternative(self, text: str) -> bool:
        from api.services.debt_collection.compliance.rules import POLITE_ALTERNATIVE

        return bool(POLITE_ALTERNATIVE.search(text))

    def _append_polite_offer(self, text: str, locale: str) -> str:
        suffix = {
            "en": " We can also discuss an installment plan if that helps.",
            "sw": " Tunaweza pia kujadili mpango wa awamu ikiwa itasaidia.",
            "mixed": " We can offer a flexible installment plan if that works better.",
        }
        extra = suffix.get(locale, suffix["mixed"])
        if extra.strip().lower() in text.lower():
            return text
        return f"{text.rstrip('.')} {extra}".strip()


_filters: ConversationFilters | None = None


def get_conversation_filters() -> ConversationFilters:
    global _filters
    if _filters is None:
        _filters = ConversationFilters()
    return _filters
