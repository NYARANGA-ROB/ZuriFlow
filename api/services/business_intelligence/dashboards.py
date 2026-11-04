"""Compose role-aware dashboard payloads from a BI snapshot."""

from __future__ import annotations

from typing import Any

from api.services.business_intelligence.privacy import strip_sensitive_metrics

DASHBOARDS = (
    "executive",
    "operations",
    "agent_performance",
    "conversation",
    "payments",
    "language",
)


def compose_dashboard(
    name: str,
    snapshot: dict[str, Any],
    insights: list[dict[str, Any]],
    *,
    include_payments: bool,
    include_excerpts: bool,
    conversations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    core = snapshot.get("core") or {}
    kenyan = snapshot.get("kenyan") or {}
    safe = strip_sensitive_metrics(snapshot, include_payments=include_payments)
    kenyan_safe = safe.get("kenyan") or kenyan

    convos = conversations or []
    if not include_excerpts:
        convos = [
            {k: v for k, v in row.items() if k != "redacted_excerpt"}
            for row in convos
        ]

    if name == "executive":
        return {
            "dashboard": name,
            "kpis": {
                "total_calls": core.get("total_calls"),
                "containment_rate": core.get("containment_rate"),
                "first_contact_resolution": core.get("first_contact_resolution"),
                "customer_sentiment": core.get("customer_sentiment"),
                "mpesa_conversion_rate": kenyan_safe.get("mpesa_conversion_rate"),
                "kes_processed": kenyan_safe.get("kes_processed") if include_payments else None,
            },
            "insights": insights[:5],
        }
    if name == "operations":
        return {
            "dashboard": name,
            "kpis": {
                "answered_calls": core.get("answered_calls"),
                "missed_calls": core.get("missed_calls"),
                "abandonment_rate": core.get("abandonment_rate"),
                "average_duration_s": core.get("average_duration_s"),
                "transfer_rate": core.get("transfer_rate"),
                "sms_followup_rate": kenyan_safe.get("sms_followup_rate"),
                "whatsapp_followup_rate": kenyan_safe.get("whatsapp_followup_rate"),
            },
            "insights": [i for i in insights if i.get("kind") in {"quality", "volume", "escalation"}],
        }
    if name == "agent_performance":
        return {
            "dashboard": name,
            "kpis": {
                "automation_rate": core.get("automation_rate"),
                "containment_rate": core.get("containment_rate"),
                "transfer_rate": core.get("transfer_rate"),
                "first_contact_resolution": core.get("first_contact_resolution"),
            },
            "intent_distribution": core.get("intent_distribution"),
            "insights": [i for i in insights if i.get("kind") == "escalation"] or insights[:3],
        }
    if name == "conversation":
        return {
            "dashboard": name,
            "kpis": {
                "category_distribution": core.get("category_distribution"),
                "intent_distribution": core.get("intent_distribution"),
                "customer_sentiment": core.get("customer_sentiment"),
            },
            "top_products": snapshot.get("top_products"),
            "conversations": convos[:50],
            "insights": [i for i in insights if i.get("kind") in {"demand", "quality"}],
        }
    if name == "payments":
        return {
            "dashboard": name,
            "kpis": {
                "mpesa_conversion_rate": kenyan_safe.get("mpesa_conversion_rate"),
                "payment_success_rate": kenyan_safe.get("payment_success_rate"),
                "payment_abandonment_rate": kenyan_safe.get("payment_abandonment_rate"),
                "kes_processed": kenyan_safe.get("kes_processed") if include_payments else None,
            },
            "insights": [i for i in insights if i.get("kind") == "payments"],
            "restricted": not include_payments,
        }
    if name == "language":
        return {
            "dashboard": name,
            "kpis": {
                "english_usage_rate": kenyan_safe.get("english_usage_rate"),
                "kiswahili_usage_rate": kenyan_safe.get("kiswahili_usage_rate"),
                "sheng_usage_rate": kenyan_safe.get("sheng_usage_rate"),
                "code_switching_rate": kenyan_safe.get("code_switching_rate"),
                "county_distribution": kenyan_safe.get("county_distribution"),
                "language_distribution": core.get("language_distribution"),
            },
            "insights": [i for i in insights if i.get("kind") == "language"],
        }
    raise ValueError(f"Unknown dashboard: {name}")
