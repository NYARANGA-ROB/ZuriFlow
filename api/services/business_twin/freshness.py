"""Freshness scoring for Digital Twin knowledge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.constants import BUSINESS_TWIN_FRESHNESS_DAYS, BUSINESS_TWIN_STALE_DAYS
from api.services.business_twin.types import KnowledgeStatus


def freshness_score(
    *,
    last_verified_at: datetime | None,
    expires_at: datetime | None = None,
    now: datetime | None = None,
    freshness_days: int = BUSINESS_TWIN_FRESHNESS_DAYS,
    stale_days: int = BUSINESS_TWIN_STALE_DAYS,
) -> tuple[float, str]:
    now = now or datetime.now(UTC)
    if expires_at is not None:
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if exp <= now:
            return 0.0, KnowledgeStatus.EXPIRED.value
    if last_verified_at is None:
        return 0.35, KnowledgeStatus.PENDING_REVIEW.value
    verified = (
        last_verified_at if last_verified_at.tzinfo else last_verified_at.replace(tzinfo=UTC)
    )
    age = now - verified
    if age <= timedelta(days=freshness_days):
        remaining = 1.0 - (age.total_seconds() / timedelta(days=freshness_days).total_seconds()) * 0.15
        return max(0.85, remaining), KnowledgeStatus.VERIFIED.value
    if age <= timedelta(days=stale_days):
        return 0.55, KnowledgeStatus.STALE.value
    return 0.2, KnowledgeStatus.EXPIRED.value


def may_answer_from_knowledge(*, status: str, risk_level: str, score: float) -> bool:
    if status in {
        KnowledgeStatus.EXPIRED.value,
        KnowledgeStatus.CONFLICTING.value,
        KnowledgeStatus.DEPRECATED.value,
    }:
        return False
    if risk_level in {"high", "critical"} and score < 0.8:
        return False
    return status == KnowledgeStatus.VERIFIED.value or (
        status == KnowledgeStatus.PENDING_REVIEW.value and risk_level == "low" and score >= 0.9
    )
