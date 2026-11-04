from __future__ import annotations

from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.sentiment import score_sentiment
from api.services.voice_analytics.types import (
    SentimentLabel,
    VoiceAnalyticsEvent,
    VoiceAnalyticsEventType,
)


def track_payment_success(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    amount: float | None = None,
    currency: str = "KES",
    receipt: str = "",
    language: str = "mixed",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.PAYMENT_SUCCESS,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=amount,
            success=True,
            language=language,
            properties={
                "amount": amount,
                "currency": currency,
                "receipt": receipt,
            },
        )
    )


def track_whatsapp_delivery(
    *,
    organization_id: int,
    success: bool,
    session_id: str = "",
    workflow_run_id: int = 0,
    message_id: int | None = None,
    latency_ms: float | None = None,
    template_name: str = "",
    language: str = "mixed",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.WHATSAPP_DELIVERY,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=latency_ms,
            success=success,
            language=language,
            properties={
                "message_id": message_id,
                "template_name": template_name,
                "delivery_latency_ms": latency_ms,
            },
        )
    )


def track_escalation(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    reason: str = "",
    intent: str = "escalation",
    queue_name: str = "",
    queue_position: int | None = None,
    language: str = "mixed",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.ESCALATION,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=float(queue_position) if queue_position is not None else None,
            success=True,
            language=language,
            labels={"intent": intent, "queue": queue_name},
            properties={"reason": reason, "queue_position": queue_position},
        )
    )


def track_interruption(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    source: str = "",
    interrupt_count: int = 1,
    language: str = "mixed",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.INTERRUPTION,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=float(interrupt_count),
            language=language,
            labels={"source": source},
            properties={"interrupt_count": interrupt_count, "source": source},
        )
    )


def track_response_latency(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    e2e_ms: float,
    stages: dict[str, float | None] | None = None,
    interrupted: bool = False,
    language: str = "mixed",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.RESPONSE_LATENCY,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=e2e_ms,
            success=not interrupted,
            language=language,
            properties={
                "e2e_ms": e2e_ms,
                "interrupted": interrupted,
                "stages": {k: v for k, v in (stages or {}).items() if v is not None},
            },
        )
    )


def track_customer_sentiment(
    *,
    organization_id: int,
    text: str,
    session_id: str = "",
    workflow_run_id: int = 0,
    language: str = "mixed",
) -> None:
    label, confidence = score_sentiment(text)
    emitter = get_voice_analytics_emitter()
    signed = {
        SentimentLabel.POSITIVE: 1.0,
        SentimentLabel.NEUTRAL: 0.0,
        SentimentLabel.NEGATIVE: -1.0,
    }[label]
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CUSTOMER_SENTIMENT,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=signed * confidence,
            language=language,
            labels={"sentiment": label.value},
            properties={
                "sentiment": label.value,
                "sentiment_score": confidence,
                "text_length": len(text),
            },
        )
    )


def track_call_started(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    language: str = "mixed",
    industry: str = "",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CALL_STARTED,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=1.0,
            success=True,
            language=language,
            properties={"industry": industry},
        )
    )


def track_call_ended(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    call_duration_seconds: float,
    language: str = "mixed",
    outcome: str = "",
) -> None:
    emitter = get_voice_analytics_emitter()
    emitter.track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CALL_ENDED,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=call_duration_seconds,
            success=True,
            language=language,
            properties={
                "call_duration_seconds": call_duration_seconds,
                "outcome": outcome,
            },
        )
    )
