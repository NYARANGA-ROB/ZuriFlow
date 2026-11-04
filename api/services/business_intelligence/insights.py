"""Turn KPI deltas into short, operator-facing insights."""

from __future__ import annotations

from typing import Any


def build_insights(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    core = snapshot.get("core") or {}
    kenyan = snapshot.get("kenyan") or {}
    products = snapshot.get("top_products") or []
    insights: list[dict[str, Any]] = []

    if products:
        name, count = products[0]
        insights.append(
            {
                "kind": "demand",
                "severity": "info",
                "headline": f"Customers frequently ask about {name}.",
                "detail": f"{count} classified conversations mentioned this product or service.",
            }
        )

    curr_fail = int(kenyan.get("payment_failures") or 0)
    prev_fail = int(kenyan.get("payment_failures_previous") or 0)
    if curr_fail > prev_fail and curr_fail > 0:
        insights.append(
            {
                "kind": "payments",
                "severity": "warning",
                "headline": "Payment failures increased versus the previous window.",
                "detail": f"{curr_fail} failed attempts this period, up from {prev_fail}.",
            }
        )

    sw = float(kenyan.get("kiswahili_usage_rate") or 0)
    en = float(kenyan.get("english_usage_rate") or 0)
    if sw > en and sw >= 0.4:
        insights.append(
            {
                "kind": "language",
                "severity": "info",
                "headline": "Most customers contacting the business use Kiswahili.",
                "detail": f"Kiswahili share is {round(sw * 100, 1)}% of classified language use.",
            }
        )

    intents = core.get("intent_distribution") or {}
    transfers = float(core.get("transfer_rate") or 0)
    if intents and transfers >= 0.25:
        top_intent = max(intents, key=intents.get)
        insights.append(
            {
                "kind": "escalation",
                "severity": "warning",
                "headline": f"Agent escalation is high for intent {top_intent}.",
                "detail": f"Transfer rate is {round(transfers * 100, 1)}%. Review automation for this intent.",
            }
        )

    fcr = float(core.get("first_contact_resolution") or 0)
    if core.get("classified_conversations") or snapshot.get("classified_conversations"):
        if fcr < 0.5 and (core.get("completed_calls") or 0) > 3:
            insights.append(
                {
                    "kind": "quality",
                    "severity": "warning",
                    "headline": "First-contact resolution is below half of classified calls.",
                    "detail": "Customers often need a second touch. Check unresolved payment and support intents.",
                }
            )

    if not insights:
        insights.append(
            {
                "kind": "volume",
                "severity": "info",
                "headline": f"{core.get('total_calls', 0)} calls in this window.",
                "detail": "Add more classified conversations to unlock language and payment insights.",
            }
        )
    return insights
