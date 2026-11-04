"""Analytics events for debt collection workflows."""

from __future__ import annotations

from api.services.voice_analytics.emitter import get_voice_analytics_emitter
from api.services.voice_analytics.types import VoiceAnalyticsEvent, VoiceAnalyticsEventType


def track_payment_commitment(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    amount: float,
    due_date: str,
    status: str = "accepted",
    language: str = "mixed",
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.PAYMENT_COMMITMENT,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=amount,
            success=status in ("accepted", "proposed"),
            language=language,
            labels={"status": status},
            properties={"amount": amount, "due_date": due_date, "status": status},
        )
    )


def track_negotiation_offer(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    offered_amount: float,
    term_months: int = 1,
    round_number: int = 1,
    acceptable: bool = True,
    language: str = "mixed",
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.NEGOTIATION_OFFER,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=offered_amount,
            success=acceptable,
            language=language,
            properties={
                "offered_amount": offered_amount,
                "term_months": term_months,
                "round_number": round_number,
                "acceptable": acceptable,
            },
        )
    )


def track_installment_scheduled(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    total_amount: float,
    installment_count: int,
    frequency: str = "monthly",
    language: str = "mixed",
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.INSTALLMENT_SCHEDULED,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=total_amount,
            success=True,
            language=language,
            properties={
                "total_amount": total_amount,
                "installment_count": installment_count,
                "frequency": frequency,
            },
        )
    )


def track_debt_escalation_risk(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    risk: str,
    reason: str,
    frustration_score: float = 0.0,
    language: str = "mixed",
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.DEBT_ESCALATION_RISK,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=frustration_score,
            success=False,
            language=language,
            labels={"risk": risk, "reason": reason},
            properties={
                "risk": risk,
                "reason": reason,
                "frustration_score": frustration_score,
            },
        )
    )


def track_compliance_event(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    action: str,
    violation_count: int,
    speaker: str,
    language: str = "mixed",
    properties: dict | None = None,
) -> None:
    event_type = (
        VoiceAnalyticsEventType.COMPLIANCE_BLOCKED
        if action in ("outbound_blocked", "agent_compliance_violation")
        else VoiceAnalyticsEventType.COMPLIANCE_VIOLATION
    )
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=event_type,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=float(violation_count),
            success=False,
            language=language,
            labels={"action": action, "speaker": speaker},
            properties={
                "action": action,
                "violation_count": violation_count,
                "speaker": speaker,
                **(properties or {}),
            },
        )
    )


def track_repayment_collected(
    *,
    organization_id: int,
    session_id: str = "",
    workflow_run_id: int = 0,
    amount: float,
    receipt: str = "",
    commitment_id: str = "",
    language: str = "mixed",
) -> None:
    get_voice_analytics_emitter().track(
        VoiceAnalyticsEvent(
            event_type=VoiceAnalyticsEventType.REPAYMENT_COLLECTED,
            organization_id=organization_id,
            session_id=session_id,
            workflow_run_id=workflow_run_id,
            value=amount,
            success=True,
            language=language,
            properties={
                "amount": amount,
                "receipt": receipt,
                "commitment_id": commitment_id,
            },
        )
    )
