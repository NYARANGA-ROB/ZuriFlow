"""Roll conversation, payment, language, and channel stats into BI KPIs."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from api.services.business_intelligence.classifier import ConversationClassification


def _rate(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 4)


def aggregate_intelligence(
    *,
    call_stats: dict[str, Any],
    payment_stats: dict[str, Any],
    classifications: Iterable[ConversationClassification | dict[str, Any]],
    kenya: dict[str, Any] | None = None,
    channels: dict[str, Any] | None = None,
    previous_payments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in classifications:
        rows.append(item.to_dict() if hasattr(item, "to_dict") else dict(item))

    total = int(call_stats.get("total_calls") or 0)
    completed = int(call_stats.get("completed_calls") or 0)
    classified = len(rows)
    answered = max(completed, classified)
    missed = max(0, total - answered)
    abandoned = missed
    transferred = sum(1 for r in rows if r.get("transferred"))
    contained = sum(1 for r in rows if r.get("contained"))
    fcr = sum(1 for r in rows if r.get("first_contact_resolved") or r.get("first_contact_resolved"))
    base = max(classified, 1)

    sentiments = Counter(r.get("sentiment") or "neutral" for r in rows)
    categories = Counter(r.get("category") or "inquiry" for r in rows)
    intents = Counter(r.get("intent") or "unknown" for r in rows)
    languages = Counter(r.get("language") or "unknown" for r in rows)
    counties = Counter(c for r in rows if (c := r.get("county")))
    products = Counter(p for r in rows if (p := r.get("requested_product")))
    code_switched = sum(1 for r in rows if r.get("code_switched"))

    kenya = kenya or {}
    lang_turns = kenya.get("language_distribution") or {}
    english = int(lang_turns.get("en") or languages.get("en") or 0)
    swahili = int(lang_turns.get("sw") or languages.get("sw") or 0)
    sheng = int(lang_turns.get("sheng") or languages.get("sheng") or 0)
    lang_den = max(english + swahili + sheng + classified, 1)

    attempts = int(payment_stats.get("attempts") or 0)
    success = int(payment_stats.get("success_count") or 0)
    abandoned_pay = int(payment_stats.get("abandoned_count") or 0)
    prev = previous_payments or {}
    prev_fail = int(prev.get("failed_count") or 0)
    curr_fail = int(payment_stats.get("failed_count") or 0)

    sms_rate = float((channels or {}).get("sms_followup_rate") or 0)
    wa_rate = float((channels or {}).get("whatsapp_followup_rate") or 0)

    core = {
        "total_calls": total,
        "answered_calls": answered,
        "missed_calls": missed,
        "completed_calls": completed,
        "average_duration_s": float(call_stats.get("avg_duration_s") or 0),
        "abandonment_rate": _rate(abandoned, total),
        "transfer_rate": _rate(transferred, classified),
        "automation_rate": _rate(contained, classified),
        "containment_rate": _rate(contained, classified),
        "first_contact_resolution": _rate(fcr, classified),
        "customer_sentiment": dict(sentiments),
        "intent_distribution": dict(intents),
        "language_distribution": dict(languages),
        "category_distribution": dict(categories),
        "classified_conversations": classified,
    }
    kenyan = {
        "english_usage_rate": _rate(english, lang_den),
        "kiswahili_usage_rate": _rate(swahili, lang_den),
        "sheng_usage_rate": _rate(sheng, lang_den)
        or float(kenya.get("sheng_usage_rate") or 0),
        "code_switching_rate": _rate(code_switched, classified)
        or float(kenya.get("code_switching_rate") or 0),
        "county_distribution": dict(counties),
        "mpesa_conversion_rate": _rate(success, max(attempts, total, 1)),
        "payment_success_rate": _rate(success, attempts),
        "kes_processed": float(payment_stats.get("kes_processed") or 0),
        "payment_abandonment_rate": _rate(abandoned_pay, attempts),
        "sms_followup_rate": sms_rate,
        "whatsapp_followup_rate": wa_rate,
        "payment_failures": curr_fail,
        "payment_failures_previous": prev_fail,
    }
    return {
        "core": core,
        "kenyan": kenyan,
        "top_products": products.most_common(8),
        "classified_conversations": classified,
        "sentiment_score": _rate(
            sentiments.get("positive", 0) - sentiments.get("negative", 0),
            base,
        ),
    }
