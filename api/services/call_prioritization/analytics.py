"""Analytics for call prioritization decisions."""

from __future__ import annotations

from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.types import VoiceAnalyticsEvent, VoiceAnalyticsEventType


def track_priority_scored(
    *,
    organization_id: int,
    customer_id: int,
    score: float,
    tier: str,
    likely_payer: bool,
    workflow_run_id: int = 0,
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CALL_PRIORITY_SCORED,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            value=score,
            success=likely_payer,
            labels={"tier": tier},
            properties={
                "customer_id": customer_id,
                "score": score,
                "tier": tier,
                "likely_payer": likely_payer,
            },
        )
    )


def track_priority_queued(
    *,
    organization_id: int,
    customer_id: int,
    score: float,
    queue_position: int,
    attempt_number: int = 1,
    workflow_run_id: int = 0,
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CALL_PRIORITY_QUEUED,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            value=score,
            success=True,
            properties={
                "customer_id": customer_id,
                "score": score,
                "queue_position": queue_position,
                "attempt_number": attempt_number,
            },
        )
    )


def track_retry_scheduled(
    *,
    organization_id: int,
    customer_id: int,
    delay_s: int,
    attempt_number: int,
    score: float,
    reason: str = "",
    workflow_run_id: int = 0,
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CALL_RETRY_SCHEDULED,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            value=float(delay_s),
            success=True,
            properties={
                "customer_id": customer_id,
                "delay_s": delay_s,
                "attempt_number": attempt_number,
                "score": score,
                "reason": reason,
            },
        )
    )


def track_call_outcome_recorded(
    *,
    organization_id: int,
    customer_id: int,
    outcome: str,
    score: float | None = None,
    workflow_run_id: int = 0,
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.CALL_OUTCOME_RECORDED,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            value=score,
            success=outcome not in ("no_answer", "busy", "failed", "voicemail"),
            labels={"outcome": outcome},
            properties={
                "customer_id": customer_id,
                "outcome": outcome,
                "score": score,
            },
        )
    )
