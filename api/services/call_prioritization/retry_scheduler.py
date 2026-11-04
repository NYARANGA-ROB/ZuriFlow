"""Retry scheduler — backoff tuned by payer likelihood and failure streaks."""

from __future__ import annotations

import math
import time

from api.services.call_prioritization.config import CallPrioritizationConfig, DEFAULT_PRIORITIZATION_CONFIG
from api.services.call_prioritization.types import (
    FAILED_OUTCOMES,
    CallOutcome,
    PrioritizationScore,
    RetrySchedule,
)


class CallRetryScheduler:
    """Schedule follow-up dials to reduce wasted attempts."""

    def __init__(self, config: CallPrioritizationConfig | None = None) -> None:
        self._config = config or DEFAULT_PRIORITIZATION_CONFIG

    def should_retry(
        self,
        *,
        attempt_number: int,
        score: float,
        outcome: str,
    ) -> bool:
        policy = self._config.retry
        if attempt_number >= policy.max_attempts:
            return False
        if score < self._config.min_score_to_call:
            return False
        if outcome == CallOutcome.PAYMENT_COLLECTED.value:
            return False
        return True

    def compute_delay_s(
        self,
        *,
        attempt_number: int,
        score: PrioritizationScore | float,
        outcome: str,
    ) -> int:
        policy = self._config.retry
        score_value = score.score if isinstance(score, PrioritizationScore) else float(score)

        base = policy.base_delay_s * (2 ** max(0, attempt_number - 1))
        base = min(base, policy.max_delay_s)

        if score_value >= policy.likely_payer_threshold:
            multiplier = policy.high_score_multiplier
        elif score_value <= policy.deprioritize_threshold:
            multiplier = policy.low_score_multiplier
        else:
            multiplier = 1.0

        if outcome in FAILED_OUTCOMES:
            multiplier *= 1.25
        elif outcome in (CallOutcome.ANSWERED.value, CallOutcome.NEGOTIATION.value):
            multiplier *= 0.75

        return int(max(300, min(policy.max_delay_s, base * multiplier)))

    def schedule(
        self,
        *,
        customer_id: int,
        organization_id: int,
        attempt_number: int,
        score: PrioritizationScore | float,
        outcome: str,
        reason: str = "call_outcome",
    ) -> RetrySchedule | None:
        score_value = score.score if isinstance(score, PrioritizationScore) else float(score)
        if not self.should_retry(
            attempt_number=attempt_number,
            score=score_value,
            outcome=outcome,
        ):
            return None

        delay_s = self.compute_delay_s(
            attempt_number=attempt_number,
            score=score,
            outcome=outcome,
        )
        return RetrySchedule(
            customer_id=customer_id,
            organization_id=organization_id,
            scheduled_at=time.time() + delay_s,
            attempt_number=attempt_number + 1,
            reason=reason,
            score=score_value,
            delay_s=delay_s,
        )

    def optimal_batch_size(self, queue_depth: int, *, concurrency_limit: int = 5) -> int:
        """Suggest dial batch size based on queue depth."""
        if queue_depth <= 0:
            return 0
        return int(min(concurrency_limit, max(1, math.ceil(queue_depth * 0.2))))
