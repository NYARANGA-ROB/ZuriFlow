"""Analytics schema — KPI definitions and event mappings for AI business calls."""

from __future__ import annotations

from typing import Any

from api.services.voice_analytics.types import VoiceAnalyticsEventType

# Canonical KPI identifiers exposed by metrics APIs.
KPI_REPAYMENT_CONVERSION = "repayment_conversion"
KPI_SUCCESSFUL_NEGOTIATIONS = "successful_negotiations"
KPI_ESCALATION_RATE = "escalation_rate"
KPI_PAYMENT_PROMISES = "payment_promises"
KPI_AVG_CALL_DURATION = "avg_call_duration"
KPI_CUSTOMER_SENTIMENT = "customer_sentiment"

BUSINESS_CALL_KPIS: tuple[str, ...] = (
    KPI_REPAYMENT_CONVERSION,
    KPI_SUCCESSFUL_NEGOTIATIONS,
    KPI_ESCALATION_RATE,
    KPI_PAYMENT_PROMISES,
    KPI_AVG_CALL_DURATION,
    KPI_CUSTOMER_SENTIMENT,
)

KPI_SCHEMA: dict[str, dict[str, Any]] = {
    KPI_REPAYMENT_CONVERSION: {
        "label": "Repayment conversion",
        "description": "Share of business calls that resulted in a collected repayment.",
        "unit": "rate",
        "numerator_events": (
            VoiceAnalyticsEventType.REPAYMENT_COLLECTED.value,
            VoiceAnalyticsEventType.PAYMENT_SUCCESS.value,
        ),
        "denominator_events": (
            VoiceAnalyticsEventType.CALL_STARTED.value,
            VoiceAnalyticsEventType.RESPONSE_LATENCY.value,
        ),
        "higher_is_better": True,
    },
    KPI_SUCCESSFUL_NEGOTIATIONS: {
        "label": "Successful negotiations",
        "description": "Negotiation offers accepted or marked successful.",
        "unit": "rate",
        "source_events": (VoiceAnalyticsEventType.NEGOTIATION_OFFER.value,),
        "success_field": "success",
        "higher_is_better": True,
    },
    KPI_ESCALATION_RATE: {
        "label": "Escalation rate",
        "description": "Calls escalated to a human or flagged high-risk.",
        "unit": "rate",
        "numerator_events": (
            VoiceAnalyticsEventType.ESCALATION.value,
            VoiceAnalyticsEventType.DEBT_ESCALATION_RISK.value,
        ),
        "denominator_events": (VoiceAnalyticsEventType.CALL_STARTED.value,),
        "higher_is_better": False,
    },
    KPI_PAYMENT_PROMISES: {
        "label": "Payment promises",
        "description": "Payment commitments or installment plans scheduled.",
        "unit": "count",
        "source_events": (
            VoiceAnalyticsEventType.PAYMENT_COMMITMENT.value,
            VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED.value,
        ),
        "higher_is_better": True,
    },
    KPI_AVG_CALL_DURATION: {
        "label": "Average call duration",
        "description": "Mean completed call length in seconds.",
        "unit": "seconds",
        "source_events": (VoiceAnalyticsEventType.CALL_ENDED.value,),
        "fallback": "workflow_runs",
        "higher_is_better": None,
    },
    KPI_CUSTOMER_SENTIMENT: {
        "label": "Customer sentiment",
        "description": "Average signed sentiment score (-1 negative to +1 positive).",
        "unit": "score",
        "source_events": (VoiceAnalyticsEventType.CUSTOMER_SENTIMENT.value,),
        "higher_is_better": True,
    },
}

# Voice analytics event types rolled into business-call aggregates.
ROLLUP_EVENT_TYPES: tuple[str, ...] = tuple(
    sorted(
        {
            VoiceAnalyticsEventType.CALL_STARTED.value,
            VoiceAnalyticsEventType.CALL_ENDED.value,
            VoiceAnalyticsEventType.REPAYMENT_COLLECTED.value,
            VoiceAnalyticsEventType.PAYMENT_SUCCESS.value,
            VoiceAnalyticsEventType.NEGOTIATION_OFFER.value,
            VoiceAnalyticsEventType.ESCALATION.value,
            VoiceAnalyticsEventType.DEBT_ESCALATION_RISK.value,
            VoiceAnalyticsEventType.PAYMENT_COMMITMENT.value,
            VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED.value,
            VoiceAnalyticsEventType.CUSTOMER_SENTIMENT.value,
            VoiceAnalyticsEventType.RESPONSE_LATENCY.value,
            VoiceAnalyticsEventType.CALL_OUTCOME_RECORDED.value,
        }
    )
)

TIMESERIES_KPIS: frozenset[str] = frozenset(
    {
        KPI_REPAYMENT_CONVERSION,
        KPI_SUCCESSFUL_NEGOTIATIONS,
        KPI_ESCALATION_RATE,
        KPI_PAYMENT_PROMISES,
        KPI_AVG_CALL_DURATION,
        KPI_CUSTOMER_SENTIMENT,
    }
)

EXPORT_COLUMNS: tuple[str, ...] = (
    "kpi",
    "label",
    "value",
    "unit",
    "count",
    "success_count",
    "rate",
)


def kpi_label(kpi: str) -> str:
    return str(KPI_SCHEMA.get(kpi, {}).get("label", kpi))
