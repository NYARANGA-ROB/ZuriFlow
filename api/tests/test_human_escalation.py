"""Tests for human escalation system."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.human_escalation.context_transfer import ContextTransferSystem
from api.services.human_escalation.escalation_queues import EscalationQueueService
from api.services.human_escalation.types import HandoffPackage


def test_priority_boost_for_high_risk():
    handoff = HandoffPackage(
        session_id="s1",
        organization_id=1,
        priority=50,
        risk_level="high",
    )
    priority = EscalationQueueService._compute_priority(handoff)
    assert priority > 50


def test_handoff_package_roundtrip():
    pkg = HandoffPackage(
        session_id="s2",
        organization_id=1,
        summary="Customer wants supervisor",
        transcript_excerpt=[{"user": "help"}],
        priority=60,
    )
    restored = HandoffPackage.from_dict(pkg.to_dict())
    assert restored.summary == pkg.summary
    assert restored.priority == 60


@pytest.mark.asyncio
async def test_context_transfer_builds_summary():
    ctx = ContextTransferSystem()
    handoff = await ctx.build_handoff(
        session_id="sess-1",
        organization_id=1,
        reason="customer_frustrated",
        extra_context="Wants manager",
    )
    assert "customer_frustrated" in handoff.summary
    assert "Wants manager" in handoff.summary


@pytest.mark.asyncio
async def test_escalation_queue_store_handoff():
    fake = MagicMock()
    pipe = MagicMock()
    fake.pipeline.return_value = pipe
    pipe.execute = AsyncMock()

    svc = EscalationQueueService(redis_client=fake)
    handoff = HandoffPackage(session_id="s3", organization_id=1, summary="test")
    await svc.store_handoff(handoff)
    pipe.execute.assert_awaited_once()


def test_compute_priority_caps_at_100():
    handoff = HandoffPackage(
        session_id="s4",
        organization_id=1,
        priority=90,
        risk_level="critical",
    )
    assert EscalationQueueService._compute_priority(handoff) == 100
