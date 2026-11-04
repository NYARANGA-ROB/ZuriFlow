"""Predictive scoring engine for collection call prioritization."""

from __future__ import annotations

from api.services.call_prioritization.config import CallPrioritizationConfig, DEFAULT_PRIORITIZATION_CONFIG
from api.services.call_prioritization.types import (
    PrioritizationScore,
    PrioritizationSignals,
    ScoreBreakdown,
)


def _tier_for_score(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    if score >= 25:
        return "low"
    return "minimal"


class CallPrioritizationScoringEngine:
    """Score customers 0–100 for outbound collection efficiency."""

    def __init__(self, config: CallPrioritizationConfig | None = None) -> None:
        self._config = config or DEFAULT_PRIORITIZATION_CONFIG

    def score(self, signals: PrioritizationSignals) -> PrioritizationScore:
        weights = self._config.weights
        breakdown = ScoreBreakdown()

        # Payment history: prior payers are likely to pay again
        payment_component = 0.0
        if signals.successful_payments > 0:
            payment_component += min(40.0, signals.successful_payments * 12.0)
        if signals.total_outstanding > 0 and signals.total_paid > 0:
            ratio = min(1.0, signals.total_paid / signals.total_outstanding)
            payment_component += ratio * 30.0
        if signals.days_since_last_payment is not None:
            if signals.days_since_last_payment <= 30:
                payment_component += 20.0
            elif signals.days_since_last_payment <= 90:
                payment_component += 10.0
        breakdown.payment_score = payment_component * weights.payment

        # Answer rate: reachable customers waste fewer dial attempts
        if signals.total_calls > 0:
            answer_rate = signals.answered_calls / signals.total_calls
        else:
            answer_rate = 0.5  # neutral prior for new accounts
        breakdown.answer_rate_score = answer_rate * 100.0 * weights.answer_rate

        # Prior conversations: engagement predicts willingness to negotiate/pay
        engagement = 0.0
        if signals.positive_conversations > 0:
            engagement += min(50.0, signals.positive_conversations * 15.0)
        if signals.days_since_last_answer is not None and signals.days_since_last_answer <= 14:
            engagement += 25.0
        breakdown.engagement_score = engagement * weights.engagement

        # Escalation frequency reduces priority (agent fatigue / compliance risk)
        escalation_pen = 0.0
        escalation_pen += min(40.0, signals.total_escalations * 8.0)
        escalation_pen += signals.unresolved_escalations * 12.0
        escalation_pen += signals.high_risk_escalations * 15.0
        breakdown.escalation_penalty = escalation_pen * weights.escalation_penalty

        # Failed attempts reduce priority and inform retry spacing
        failure_pen = min(50.0, signals.consecutive_failures * 12.0 + signals.failed_calls * 2.0)
        breakdown.failure_penalty = failure_pen * weights.failure_penalty

        # Recency: recently engaged debtors may convert faster
        if signals.days_past_due <= 30:
            breakdown.recency_bonus = 8.0
        elif signals.days_past_due <= 60:
            breakdown.recency_bonus = 4.0

        total = breakdown.total
        tier = _tier_for_score(total)
        likely_payer = total >= self._config.retry.likely_payer_threshold

        return PrioritizationScore(
            customer_id=signals.customer_id,
            organization_id=signals.organization_id,
            score=total,
            tier=tier,
            breakdown=breakdown,
            signals=signals,
            likely_payer=likely_payer,
        )
