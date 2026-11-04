"""Feature extraction from CRM history for prioritization scoring."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.services.call_prioritization.types import (
    ANSWERED_OUTCOMES,
    FAILED_OUTCOMES,
    PrioritizationSignals,
)

POSITIVE_OUTCOMES = frozenset(
    {
        *ANSWERED_OUTCOMES,
        "negotiation",
        "payment_collected",
        "installment_scheduled",
    }
)


def _days_since(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - dt
    return max(0, delta.days)


def _consecutive_failures(calls: list[dict[str, Any]]) -> int:
    """Count trailing failed call outcomes (most recent first)."""
    count = 0
    for call in calls:
        outcome = (call.get("outcome") or "").lower()
        if outcome in FAILED_OUTCOMES:
            count += 1
        elif outcome in ANSWERED_OUTCOMES:
            break
        elif outcome:
            break
    return count


def build_signals_from_profile(profile: dict[str, Any]) -> PrioritizationSignals:
    """Derive prioritization signals from a CustomerProfile dict."""
    payments = profile.get("payment_history") or []
    calls = profile.get("call_history") or []
    escalations = profile.get("escalation_history") or []
    debt_accounts = profile.get("debt_accounts") or []

    successful = [p for p in payments if p.get("status") == "success"]
    total_paid = sum(float(p.get("amount") or 0) for p in successful)
    last_payment_at = None
    if successful:
        paid_dates = [p.get("paid_at") for p in successful if p.get("paid_at")]
        if paid_dates:
            last_payment_at = max(paid_dates)

    answered = [
        c
        for c in calls
        if (c.get("outcome") or "").lower() in ANSWERED_OUTCOMES
    ]
    failed = [
        c for c in calls if (c.get("outcome") or "").lower() in FAILED_OUTCOMES
    ]
    positive = [
        c
        for c in calls
        if (c.get("outcome") or "").lower() in POSITIVE_OUTCOMES
    ]

    last_answer_at = None
    if answered:
        answer_times = [
            c.get("started_at") or c.get("created_at")
            for c in answered
            if c.get("started_at") or c.get("created_at")
        ]
        if answer_times:
            last_answer_at = max(answer_times)

    unresolved = [e for e in escalations if not e.get("resolved")]
    high_risk = [
        e for e in escalations if (e.get("risk_level") or "").lower() in ("high", "critical")
    ]

    max_dpd = max((int(a.get("days_past_due") or 0) for a in debt_accounts), default=0)
    total_outstanding = float(profile.get("total_outstanding") or 0.0)

    sorted_calls = sorted(
        calls,
        key=lambda c: c.get("started_at") or c.get("created_at") or "",
        reverse=True,
    )

    last_payment_dt = None
    if last_payment_at:
        try:
            last_payment_dt = datetime.fromisoformat(str(last_payment_at).replace("Z", "+00:00"))
        except ValueError:
            last_payment_dt = None

    last_answer_dt = None
    if last_answer_at:
        try:
            last_answer_dt = datetime.fromisoformat(str(last_answer_at).replace("Z", "+00:00"))
        except ValueError:
            last_answer_dt = None

    return PrioritizationSignals(
        customer_id=int(profile["id"]),
        organization_id=int(profile["organization_id"]),
        phone_e164=str(profile["phone_e164"]),
        full_name=str(profile.get("full_name") or ""),
        preferred_locale=str(profile.get("preferred_locale") or "mixed"),
        total_outstanding=total_outstanding,
        days_past_due=max_dpd,
        successful_payments=len(successful),
        total_paid=total_paid,
        days_since_last_payment=_days_since(last_payment_dt),
        total_calls=len(calls),
        answered_calls=len(answered),
        failed_calls=len(failed),
        days_since_last_answer=_days_since(last_answer_dt),
        positive_conversations=len(positive),
        total_escalations=len(escalations),
        unresolved_escalations=len(unresolved),
        high_risk_escalations=len(high_risk),
        consecutive_failures=_consecutive_failures(sorted_calls),
    )
