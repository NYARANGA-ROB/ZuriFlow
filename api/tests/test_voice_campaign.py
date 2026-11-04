"""Tests for voice campaign management engine."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from api.services.voice_campaign.retry_engine import CampaignRetryEngine
from api.services.voice_campaign.scheduler import CampaignScheduler
from api.services.voice_campaign.throttling import CampaignThrottler


def _campaign(**kwargs):
    defaults = {
        "id": 1,
        "orchestrator_metadata": {
            "schedule_config": {
                "enabled": True,
                "timezone": "Africa/Nairobi",
                "slots": [{"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}],
            }
        },
        "rate_limit_per_second": 2,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_scheduler_within_campaign_window():
    scheduler = CampaignScheduler()
    campaign = _campaign()
    monday_10am = datetime(2026, 6, 22, 10, 0, tzinfo=ZoneInfo("Africa/Nairobi"))
    assert scheduler.is_within_campaign_schedule(campaign, now=monday_10am) is True


def test_scheduler_outside_campaign_window():
    scheduler = CampaignScheduler()
    campaign = _campaign()
    monday_8am = datetime(2026, 6, 22, 8, 0, tzinfo=ZoneInfo("Africa/Nairobi"))
    assert scheduler.is_within_campaign_schedule(campaign, now=monday_8am) is False


def test_scheduler_deferred_start():
    scheduler = CampaignScheduler()
    future = (datetime.now(UTC)).isoformat()
    campaign = _campaign(
        orchestrator_metadata={"scheduled_start_at": "2099-01-01T00:00:00+00:00"}
    )
    assert scheduler.is_campaign_started(campaign) is False


def test_scheduler_resolve_locale():
    scheduler = CampaignScheduler()
    assert scheduler.resolve_locale({"preferred_locale": "sw"}) == "sw"
    assert scheduler.resolve_locale({}) == "mixed"


def test_retry_engine_delay_shorter_for_high_priority():
    engine = CampaignRetryEngine()
    high = engine.compute_delay_s(retry_count=2, retry_config=None, priority_score=80.0)
    low = engine.compute_delay_s(retry_count=2, retry_config=None, priority_score=20.0)
    assert high < low


def test_retry_engine_respects_max_retries():
    engine = CampaignRetryEngine()
    assert engine.should_retry(reason="busy", retry_count=2, retry_config={"max_retries": 2}) is False


def test_throttler_batch_size():
    throttler = CampaignThrottler()
    campaign = _campaign(orchestrator_metadata={"max_concurrency": 3, "throttle": {"batch_size": 10}})
    from api.services.voice_campaign.config import ThrottleConfig

    throttle = ThrottleConfig.from_campaign(campaign)
    assert throttler.compute_batch_size(throttle, queue_depth=50) <= 6


@pytest.mark.asyncio
async def test_outbound_queue_stats(monkeypatch):
    from api.services.voice_campaign.outbound_queue import OutboundCampaignQueue

    async def fake_breakdown(campaign_id):
        return {"queued": 5, "processed": 10, "processing": 1}

    monkeypatch.setattr(
        "api.services.voice_campaign.outbound_queue.db_client.get_queued_run_state_breakdown",
        fake_breakdown,
    )
    monkeypatch.setattr(
        "api.services.voice_campaign.outbound_queue.db_client.get_scheduled_runs_count",
        AsyncMock(return_value=2),
    )

    stats = await OutboundCampaignQueue().stats(1)
    assert stats.queued == 5
    assert stats.scheduled_retries == 2
    assert stats.total == 16
