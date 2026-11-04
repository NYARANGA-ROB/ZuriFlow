"""ARQ tasks for call reliability recovery workers."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from api.services.call_reliability.service import get_call_reliability_service


async def process_call_reliability_retries(
    ctx, payload: dict[str, Any]
) -> dict[str, Any]:
    """Drain due retry jobs for one or more organizations."""
    _ = ctx
    org_ids = payload.get("organization_ids") or []
    if not org_ids and payload.get("organization_id"):
        org_ids = [int(payload["organization_id"])]

    svc = get_call_reliability_service()
    results = []
    for org_id in org_ids:
        result = await svc.process_retries(int(org_id))
        results.append(result)
        logger.info(
            "call reliability retries org={} claimed={} ok={} failed={}",
            org_id,
            result.get("claimed"),
            result.get("succeeded"),
            result.get("failed"),
        )
    return {"organizations": len(results), "results": results}


async def process_all_call_reliability_retries(ctx) -> dict[str, Any]:
    """Scan retry queue keys and process all active organizations."""
    _ = ctx
    import redis.asyncio as aioredis

    from api.constants import REDIS_URL

    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    org_ids: set[int] = set()
    async for key in redis.scan_iter(match="call_reliability:retry:*", count=100):
        try:
            org_ids.add(int(key.rsplit(":", 1)[-1]))
        except ValueError:
            continue
    if not org_ids:
        return {"organizations": 0, "processed_at": time.time()}
    return await process_call_reliability_retries(
        ctx, {"organization_ids": sorted(org_ids)}
    )
