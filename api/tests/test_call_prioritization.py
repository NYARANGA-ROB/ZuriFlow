"""Tests for predictive call prioritization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.call_prioritization.config import CallPrioritizationConfig
from api.services.call_prioritization.features import build_signals_from_profile
from api.services.call_prioritization.retry_scheduler import CallRetryScheduler
from api.services.call_prioritization.scoring import CallPrioritizationScoringEngine
from api.services.call_prioritization.types import PrioritizationSignals, PrioritizedCallEntry


def _signals(**kwargs) -> PrioritizationSignals:
    defaults = dict(
        customer_id=1,
        organization_id=1,
        phone_e164="+254712345678",
        full_name="Jane",
    )
    defaults.update(kwargs)
    return PrioritizationSignals(**defaults)


def test_scoring_prioritizes_likely_payer():
    engine = CallPrioritizationScoringEngine()
    likely = engine.score(
        _signals(
            successful_payments=3,
            total_paid=9000.0,
            total_outstanding=10000.0,
            days_since_last_payment=10,
            answered_calls=4,
            total_calls=5,
            positive_conversations=3,
            days_since_last_answer=3,
        )
    )
    unlikely = engine.score(
        _signals(
            consecutive_failures=4,
            failed_calls=6,
            total_calls=7,
            answered_calls=1,
            total_escalations=3,
            unresolved_escalations=2,
            high_risk_escalations=1,
        )
    )
    assert likely.score > unlikely.score
    assert likely.likely_payer is True
    assert unlikely.tier in ("low", "minimal")


def test_scoring_new_customer_neutral_prior():
    engine = CallPrioritizationScoringEngine()
    result = engine.score(_signals())
    assert 20.0 <= result.score <= 60.0


def test_features_from_profile():
    profile = {
        "id": 1,
        "organization_id": 1,
        "phone_e164": "+254700000001",
        "full_name": "John",
        "preferred_locale": "sw",
        "total_outstanding": 5000.0,
        "debt_accounts": [{"days_past_due": 45, "outstanding_balance": 5000.0}],
        "payment_history": [
            {"status": "success", "amount": 1000.0, "paid_at": "2026-06-01T10:00:00+00:00"}
        ],
        "call_history": [
            {"outcome": "answered", "started_at": "2026-06-10T10:00:00+00:00"},
            {"outcome": "no_answer", "started_at": "2026-06-09T10:00:00+00:00"},
        ],
        "escalation_history": [{"resolved": False, "risk_level": "high"}],
    }
    signals = build_signals_from_profile(profile)
    assert signals.successful_payments == 1
    assert signals.answered_calls == 1
    assert signals.failed_calls == 1
    assert signals.unresolved_escalations == 1


def test_retry_scheduler_shorter_delay_for_high_score():
    scheduler = CallRetryScheduler()
    high_delay = scheduler.compute_delay_s(attempt_number=2, score=80.0, outcome="no_answer")
    low_delay = scheduler.compute_delay_s(attempt_number=2, score=20.0, outcome="no_answer")
    assert high_delay < low_delay


def test_retry_scheduler_stops_after_max_attempts():
    scheduler = CallRetryScheduler()
    assert scheduler.should_retry(attempt_number=6, score=90.0, outcome="no_answer") is False


def test_retry_scheduler_skips_after_payment():
    scheduler = CallRetryScheduler()
    assert scheduler.should_retry(attempt_number=1, score=90.0, outcome="payment_collected") is False


@pytest.mark.asyncio
async def test_prioritization_queue_enqueue():
    from api.services.call_prioritization.queue import PrioritizationQueue

    fake = AsyncMock()
    fake.zcard = AsyncMock(return_value=0)
    fake.pipeline = MagicMock(return_value=fake)
    fake.zadd = AsyncMock()
    fake.expire = AsyncMock()
    fake.setex = AsyncMock()
    fake.execute = AsyncMock()
    fake.zrevrank = AsyncMock(return_value=0)

    svc = PrioritizationQueue(redis_client=fake, ttl_s=60)
    entry = PrioritizedCallEntry(
        customer_id=1,
        organization_id=1,
        phone_e164="+254712345678",
        full_name="Jane",
        score=72.5,
        tier="medium",
    )
    ok, position = await svc.enqueue(entry)
    assert ok is True
    assert position == 1


@pytest.fixture
async def org(async_session):
    from api.db.models import OrganizationModel

    organization = OrganizationModel(provider_id="test-org-prioritization")
    async_session.add(organization)
    await async_session.flush()
    return organization


@pytest.mark.asyncio
async def test_prioritization_service_score_customer(db_session, org):
    from api.services.call_prioritization.service import CallPrioritizationService
    from api.services.crm.service import get_customer_service

    crm = get_customer_service()
    profile = await crm.create_customer(
        organization_id=org.id,
        phone_e164="+254755555555",
        full_name="Alice",
        debt_account={
            "account_reference": "LOAN-10",
            "outstanding_balance": 8000.0,
        },
    )
    await crm.record_payment(
        profile.id,
        organization_id=org.id,
        amount=2000.0,
    )
    svc = CallPrioritizationService()
    scored = await svc.score_customer(profile.id, organization_id=org.id)
    assert scored is not None
    assert scored.score > 0
    assert scored.tier in ("high", "medium", "low", "minimal")
