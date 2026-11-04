"""ARQ tasks for business call analytics aggregation."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from api.services.business_call_analytics.service import get_business_call_analytics_service


async def aggregate_business_call_analytics(
    ctx, payload: dict[str, Any]
) -> dict[str, Any]:
    """Roll up business-call KPIs for one or more organizations."""
    _ = ctx
    org_ids = payload.get("organization_ids") or []
    if not org_ids and payload.get("organization_id"):
        org_ids = [int(payload["organization_id"])]

    from_ts = payload.get("from_ts")
    to_ts = payload.get("to_ts", time.time())
    svc = get_business_call_analytics_service()
    results = []
    for org_id in org_ids:
        snapshot = await svc.trigger_aggregate(
            int(org_id),
            from_ts=from_ts,
            to_ts=to_ts,
        )
        results.append(snapshot.to_dict())
        logger.info(
            "business call analytics aggregate org={} calls={} kpis={}",
            org_id,
            snapshot.total_calls,
            list(snapshot.kpis.keys()),
        )
    return {"organizations": len(results), "results": results}


async def aggregate_all_business_call_analytics(ctx) -> dict[str, Any]:
    """Scan voice analytics org keys and aggregate business KPIs."""
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
    return await aggregate_business_call_analytics(
        ctx,
        {"organization_ids": sorted(org_ids), "to_ts": time.time()},
    )
