"""Heuristic conversation classification for Kenyan voice and chat."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from api.services.business_intelligence.privacy import redact_text

CATEGORIES = (
    "sales",
    "support",
    "payment",
    "complaint",
    "booking",
    "cancellation",
    "inquiry",
    "escalation",
)

_CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "payment": (
        "pay",
        "payment",
        "lipa",
        "mpesa",
        "m-pesa",
        "paybill",
        "till",
        "pesa",
        "balance",
        "receipt",
    ),
    "complaint": (
        "complaint",
        "complain",
        "angry",
        "shida",
        "worst",
        "refund",
        "harassed",
        "late",
        "never",
    ),
    "booking": (
        "book",
        "booking",
        "appointment",
        "reservation",
        "schedule",
        "miadi",
    ),
    "cancellation": (
        "cancel",
        "cancellation",
        "sitisha",
        "abort",
        "unsubscribe",
    ),
    "sales": (
        "buy",
        "price",
        "bei",
        "offer",
        "package",
        "upgrade",
        "quote",
        "order",
        "nunua",
    ),
    "support": (
        "help",
        "issue",
        "not working",
        "haifanyi",
        "broken",
        "reset",
        "howto",
        "how do",
    ),
    "escalation": (
        "supervisor",
        "manager",
        "human",
        "agent",
        "speak to someone",
        "transfer",
        "eskalate",
        "escalate",
    ),
    "inquiry": (
        "where",
        "when",
        "hours",
        "location",
        "wapi",
        "linakuwa",
        "info",
        "information",
    ),
}

_SWAHILI = (
    "sawa",
    "asante",
    "karibu",
    "habari",
    "tafadhali",
    "ndiyo",
    "hapana",
    "pesa",
    "bei",
    "shida",
    "sasa",
    "leo",
    "kesho",
    "pole",
    "sana",
    "nataka",
    "kulipa",
    "nisaidie",
)
_SHENG = (
    "niaje",
    "msee",
    "poa",
    "rada",
    "noma",
    "waba",
    "mdosi",
    "keja",
    "mbele",
    "chapaa",
    "ngori",
)
_ENGLISH = (
    "please",
    "thank",
    "hello",
    "yes",
    "want",
    "need",
    "help",
    "pay",
    "book",
    "cancel",
)

_PRODUCT = re.compile(
    r"\b(loan|wifi|fibre|token|tokens|airtime|package|policy|premium|account)\b",
    re.I,
)


@dataclass
class ConversationClassification:
    category: str
    intent: str
    sentiment: str
    outcome: str
    unresolved_issue: str | None
    requested_product: str | None
    next_action: str | None
    language: str
    code_switched: bool
    contained: bool
    transferred: bool
    first_contact_resolved: bool
    redacted_excerpt: str | None
    county: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "outcome": self.outcome,
            "unresolved_issue": self.unresolved_issue,
            "requested_product": self.requested_product,
            "next_action": self.next_action,
            "language": self.language,
            "code_switched": self.code_switched,
            "contained": self.contained,
            "transferred": self.transferred,
            "first_contact_resolved": self.first_contact_resolved,
            "redacted_excerpt": self.redacted_excerpt,
            "county": self.county,
            "metadata": dict(self.metadata),
        }


def _score_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in text)


def classify_conversation(
    text: str,
    *,
    context: dict[str, Any] | None = None,
    transferred: bool = False,
    completed: bool = False,
    county: str | None = None,
) -> ConversationClassification:
    blob = (text or "").strip().lower()
    ctx = context or {}
    scores = {name: _score_terms(blob, terms) for name, terms in _CATEGORY_TERMS.items()}
    if transferred:
        scores["escalation"] += 2
    category = max(scores, key=scores.get)
    if scores[category] == 0:
        category = "inquiry"

    sw = _score_terms(blob, _SWAHILI)
    sh = _score_terms(blob, _SHENG)
    en = _score_terms(blob, _ENGLISH)
    present = [name for name, n in (("sw", sw), ("en", en), ("sheng", sh)) if n > 0]
    if sh >= sw and sh >= en and sh > 0:
        language = "sheng"
    elif sw > en:
        language = "sw"
    elif en > 0:
        language = "en"
    else:
        language = str(ctx.get("language") or "unknown")
    code_switched = len(present) >= 2 or bool(ctx.get("code_switched"))

    from api.services.voice_analytics.sentiment import score_sentiment

    _label, _confidence = score_sentiment(blob)
    sentiment = _label.value if hasattr(_label, "value") else str(_label)

    product_match = _PRODUCT.search(blob)
    requested = product_match.group(1).lower() if product_match else None

    unresolved = None
    if category in {"complaint", "support", "escalation"} and not completed:
        unresolved = redact_text(blob[:160])
    if "fail" in blob or "haifanyi" in blob:
        unresolved = unresolved or "Reported failure during the conversation"

    if transferred:
        outcome = "transferred"
        next_action = "Human follow-up"
    elif category == "payment" and ("success" in blob or "received" in blob):
        outcome = "paid"
        next_action = None
    elif completed and category not in {"complaint", "escalation"}:
        outcome = "resolved"
        next_action = None
    elif category == "booking":
        outcome = "booking_requested"
        next_action = "Confirm appointment"
    elif category == "payment":
        outcome = "payment_attempted"
        next_action = "Retry M-Pesa if unpaid"
    else:
        outcome = "open" if not completed else "completed"
        next_action = "Follow up" if not completed else None

    contained = completed and not transferred and category != "escalation"
    fcr = contained and unresolved is None and category not in {"escalation", "complaint"}

    intent = str(ctx.get("intent") or category)
    excerpt = redact_text(text)

    return ConversationClassification(
        category=category,
        intent=intent,
        sentiment=sentiment,
        outcome=outcome,
        unresolved_issue=unresolved,
        requested_product=requested,
        next_action=next_action,
        language=language,
        code_switched=code_switched,
        contained=contained,
        transferred=transferred,
        first_contact_resolved=fcr,
        redacted_excerpt=excerpt,
        county=county or ctx.get("county"),
        metadata={
            "swahili_hits": sw,
            "english_hits": en,
            "sheng_hits": sh,
            "code_switched": code_switched,
        },
    )
