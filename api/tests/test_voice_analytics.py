"""Tests for voice workflow analytics."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api.services.voice_analytics.schema import normalize_event, validate_event_payload
from api.services.voice_analytics.sentiment import score_sentiment
from api.services.voice_analytics.types import (
    SentimentLabel,
    VoiceAnalyticsEvent,
    VoiceAnalyticsEventType,
)


def test_validate_event_payload():
    assert validate_event_payload({}) == [
        "missing required field: event_type",
        "missing required field: organization_id",
    ]
    assert not validate_event_payload(
        {"event_type": "payment_success", "organization_id": 1}
    )


def test_normalize_payment_event():
    event = normalize_event(
        {
            "event_type": "payment_success",
            "organization_id": 1,
            "session_id": "sess-1",
            "value": 500.0,
            "success": True,
            "properties": {"currency": "KES"},
        }
    )
    assert event.event_type == VoiceAnalyticsEventType.PAYMENT_SUCCESS
    assert event.value == 500.0


def test_sentiment_positive_swahili():
    label, confidence = score_sentiment("asante sana umesaidia")
    assert label == SentimentLabel.POSITIVE
    assert confidence > 0.5


def test_sentiment_negative():
    label, _ = score_sentiment("this is terrible I have a problem")
    assert label == SentimentLabel.NEGATIVE


def test_sentiment_neutral():
    label, _ = score_sentiment("hello")
    assert label == SentimentLabel.NEUTRAL


@pytest.mark.asyncio
async def test_store_append_event():
    from api.services.voice_analytics.store import VoiceAnalyticsStore

    fake = AsyncMock()
    fake.pipeline = lambda: fake
    fake.lpush = AsyncMock()
    fake.ltrim = AsyncMock()
    fake.expire = AsyncMock()
    fake.setex = AsyncMock()
    fake.execute = AsyncMock()
    fake.hincrby = AsyncMock()
    fake.hincrbyfloat = AsyncMock()
    fake.hsetnx = AsyncMock()
    fake.hget = AsyncMock(return_value=None)

    store = VoiceAnalyticsStore(redis_client=fake, event_ttl_s=60)
    event = VoiceAnalyticsEvent(
        event_type=VoiceAnalyticsEventType.INTERRUPTION,
        organization_id=1,
        session_id="sess-1",
        value=1.0,
    )
    await store.append_event(event)
    fake.lpush.assert_called()
