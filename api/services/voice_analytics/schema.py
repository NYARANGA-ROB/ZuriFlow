"""Validation helpers for voice analytics events."""

from __future__ import annotations

from typing import Any

from api.services.voice_analytics.types import VoiceAnalyticsEvent, VoiceAnalyticsEventType

_REQUIRED_FIELDS = ("event_type", "organization_id")

_EVENT_VALUE_HINTS: dict[VoiceAnalyticsEventType, str] = {
    VoiceAnalyticsEventType.PAYMENT_SUCCESS: "amount",
    VoiceAnalyticsEventType.WHATSAPP_DELIVERY: "delivery_latency_ms",
    VoiceAnalyticsEventType.ESCALATION: "queue_position",
    VoiceAnalyticsEventType.INTERRUPTION: "interrupt_count",
    VoiceAnalyticsEventType.RESPONSE_LATENCY: "e2e_ms",
    VoiceAnalyticsEventType.CUSTOMER_SENTIMENT: "sentiment_score",
    VoiceAnalyticsEventType.PAYMENT_COMMITMENT: "amount",
    VoiceAnalyticsEventType.NEGOTIATION_OFFER: "offered_amount",
    VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED: "total_amount",
    VoiceAnalyticsEventType.DEBT_ESCALATION_RISK: "frustration_score",
    VoiceAnalyticsEventType.REPAYMENT_COLLECTED: "amount",
    VoiceAnalyticsEventType.CALL_PRIORITY_SCORED: "score",
    VoiceAnalyticsEventType.CALL_PRIORITY_QUEUED: "score",
    VoiceAnalyticsEventType.CALL_RETRY_SCHEDULED: "delay_s",
    VoiceAnalyticsEventType.CALL_OUTCOME_RECORDED: "score",
    VoiceAnalyticsEventType.CAMPAIGN_EVENT: "processed",
    VoiceAnalyticsEventType.COMPLIANCE_VIOLATION: "violation_count",
    VoiceAnalyticsEventType.COMPLIANCE_BLOCKED: "violation_count",
    VoiceAnalyticsEventType.CALL_STARTED: "call_count",
    VoiceAnalyticsEventType.CALL_ENDED: "call_duration_seconds",
}


def validate_event_payload(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data or data[field] in (None, ""):
            errors.append(f"missing required field: {field}")
    if "event_type" in data:
        try:
            VoiceAnalyticsEventType(data["event_type"])
        except ValueError:
            errors.append(f"invalid event_type: {data['event_type']}")
    if "organization_id" in data:
        try:
            if int(data["organization_id"]) <= 0:
                errors.append("organization_id must be positive")
        except (TypeError, ValueError):
            errors.append("organization_id must be an integer")
    return errors


def normalize_event(data: dict[str, Any]) -> VoiceAnalyticsEvent:
    errors = validate_event_payload(data)
    if errors:
        raise ValueError("; ".join(errors))
    event = VoiceAnalyticsEvent.from_dict(data)
    hint = _EVENT_VALUE_HINTS.get(event.event_type)
    if event.value is None and hint and hint in event.properties:
        try:
            event.value = float(event.properties[hint])
        except (TypeError, ValueError):
            pass
    return event
