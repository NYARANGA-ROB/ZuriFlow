"""Cost analytics aggregation for voice optimization."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.voice_cost_optimization.token_tracker import TokenTracker
from api.services.voice_cost_optimization.types import CostAnalyticsSnapshot


class VoiceCostAnalytics:
    """Roll up per-org savings from caching, prerecorded, and token budgets."""

    def __init__(self, tracker: TokenTracker | None = None) -> None:
        self._tracker = tracker or TokenTracker()
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    async def aggregate_organization(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ) -> CostAnalyticsSnapshot:
        now = time.time()
        start = from_ts if from_ts is not None else now - 86400 * 7
        end = to_ts if to_ts is not None else now

        redis = await self._get_redis()
        totals = {
            "llm_calls": 0,
            "cache_hits": 0,
            "prerecorded_hits": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tokens_saved": 0,
            "estimated_cost_usd": 0.0,
            "sessions": 0,
            "tts_characters": 0,
        }

        cursor = datetime.fromtimestamp(start, tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        while cursor <= end_dt:
            bucket = cursor.strftime("%Y%m%d")
            key = f"voice_cost:org:{organization_id}:{bucket}"
            data = await redis.hgetall(key)
            if data:
                totals["llm_calls"] += int(data.get("llm_calls", 0))
                totals["cache_hits"] += int(data.get("cache_hits", 0))
                totals["prerecorded_hits"] += int(data.get("prerecorded_hits", 0))
                totals["input_tokens"] += int(data.get("input_tokens", 0))
                totals["output_tokens"] += int(data.get("output_tokens", 0))
                totals["tokens_saved"] += int(data.get("tokens_saved", 0))
                totals["estimated_cost_usd"] += float(
                    data.get("estimated_cost_usd", 0.0)
                )
                totals["sessions"] += int(data.get("sessions", 0))
            cursor += timedelta(days=1)

        avoided = totals["cache_hits"] + totals["prerecorded_hits"]
        savings_usd = (totals["tokens_saved"] / 1_000_000) * 0.60 + (
            avoided * 0.002
        )

        return CostAnalyticsSnapshot(
            organization_id=organization_id,
            from_ts=start,
            to_ts=end,
            generated_at=now,
            total_sessions=totals["sessions"],
            llm_calls=totals["llm_calls"],
            cache_hits=totals["cache_hits"],
            prerecorded_hits=totals["prerecorded_hits"],
            tts_characters=totals["tts_characters"],
            tts_generations_avoided=avoided,
            input_tokens=totals["input_tokens"],
            output_tokens=totals["output_tokens"],
            tokens_saved=totals["tokens_saved"],
            estimated_cost_usd=totals["estimated_cost_usd"],
            estimated_savings_usd=round(savings_usd, 4),
        )

    async def session_summary(self, session_id: str) -> dict[str, Any]:
        record = await self._tracker.get_session_record(session_id)
        if record is None:
            return {"session_id": session_id, "found": False}
        return {"found": True, **record.to_dict()}


_analytics: VoiceCostAnalytics | None = None


def get_voice_cost_analytics() -> VoiceCostAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = VoiceCostAnalytics()
    return _analytics
