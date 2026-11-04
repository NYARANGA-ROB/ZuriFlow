"""Deep health checks for load balancers and Kubernetes readiness probes."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text

from api.constants import REDIS_URL
from api.db import db_client


async def check_database() -> tuple[bool, str]:
    try:
        async with db_client.async_session() as session:
            await session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def check_redis() -> tuple[bool, str]:
    try:
        client = await aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            pong = await client.ping()
            if not pong:
                return False, "ping returned false"
            return True, "ok"
        finally:
            await client.aclose()
    except Exception as exc:
        return False, str(exc)


async def readiness_report() -> dict[str, Any]:
    db_ok, db_detail = await check_database()
    redis_ok, redis_detail = await check_redis()
    ready = db_ok and redis_ok
    return {
        "ready": ready,
        "checks": {
            "database": {"ok": db_ok, "detail": db_detail},
            "redis": {"ok": redis_ok, "detail": redis_detail},
        },
    }
