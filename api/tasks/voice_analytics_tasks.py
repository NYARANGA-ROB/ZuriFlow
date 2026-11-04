"""ARQ tasks for voice analytics ingestion and aggregation."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from api.services.voice_analytics.aggregator import VoiceAnalyticsAggregator
from api.services.voice_analytics.pipeline import VoiceAnalyticsPipeline
from api.services.voice_analytics.schema import normalize_event
from api.services.voice_analytics.store import VoiceAnalyticsStore


async def ingest_voice_analytics_event(ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Durable ingest path for events emitted from ARQ workers."""
    _ = ctx
    event = normalize_event(payload)
    pipeline = VoiceAnalyticsPipeline()
    await pipeline.ingest(event)
    await VoiceAnalyticsPipeline.forward_posthog(event)
    return {"event_id": event.event_id, "stored": True}


async def aggregate_voice_analytics(ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Roll up voice analytics for one or more organizations."""
    _ = ctx
    org_ids = payload.get("organization_ids") or []
    if not org_ids and payload.get("organization_id"):
        org_ids = [int(payload["organization_id"])]

    from_ts = payload.get("from_ts")
    to_ts = payload.get("to_ts", time.time())
    aggregator = VoiceAnalyticsAggregator()
    results = []
    for org_id in org_ids:
        summary = await aggregator.aggregate_organization(
            int(org_id),
            from_ts=from_ts,
            to_ts=to_ts,
        )
        results.append(summary)
        logger.info(
            "voice analytics aggregate org={} metrics={}",
            org_id,
            list(summary.get("metrics", {}).keys()),
        )
    return {"organizations": len(results), "results": results}


async def aggregate_all_voice_analytics(ctx) -> dict[str, Any]:
    """Scan recent event keys and aggregate active organizations."""
    _ = ctx
    import redis.asyncio as aioredis

    from api.constants import REDIS_URL

    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    org_ids: set[int] = set()
    async for key in redis.scan_iter(match="voice_analytics:events:*", count=100):
        try:
            org_ids.add(int(key.rsplit(":", 1)[-1]))
        except ValueError:
            continue
    if not org_ids:
        return {"organizations": 0}
    return await aggregate_voice_analytics(
        ctx,
        {"organization_ids": sorted(org_ids), "to_ts": time.time()},
    )
