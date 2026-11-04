"""Usage analytics for public API requests."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from loguru import logger
from starlette.requests import Request
from starlette.responses import Response

import redis.asyncio as aioredis

from api.constants import PUBLIC_API_USAGE_TTL_S, REDIS_URL
from api.services.public_api.types import PublicApiContext, UsageBucket


class PublicApiUsageTracker:
    """Redis-backed counters for per-org API usage."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    def _day_key(self, organization_id: int) -> str:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"public_api:usage:{organization_id}:{day}"

    def _key_day_key(self, organization_id: int, api_key_id: int) -> str:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"public_api:usage:{organization_id}:key:{api_key_id}:{day}"

    async def record(
        self,
        ctx: PublicApiContext,
        request: Request,
        response: Response,
        *,
        latency_ms: float,
    ) -> None:
        try:
            client = await self._client()
            org_key = self._day_key(ctx.organization_id)
            key_key = self._key_day_key(ctx.organization_id, ctx.api_key_id)
            path = _normalize_path(request.url.path)
            is_error = response.status_code >= 400

            pipe = client.pipeline()
            for redis_key in (org_key, key_key):
                pipe.hincrby(redis_key, "total_requests", 1)
                if is_error:
                    pipe.hincrby(redis_key, "error_requests", 1)
                pipe.hincrbyfloat(redis_key, "total_latency_ms", round(latency_ms, 2))
                pipe.hincrby(redis_key, f"path:{path}", 1)
                pipe.expire(redis_key, PUBLIC_API_USAGE_TTL_S)
            await pipe.execute()
        except Exception as exc:
            logger.debug(f"Public API usage tracking skipped: {exc}")

    async def get_summary(
        self,
        organization_id: int,
        *,
        api_key_id: int | None = None,
    ) -> UsageBucket:
        try:
            client = await self._client()
            redis_key = (
                self._key_day_key(organization_id, api_key_id)
                if api_key_id is not None
                else self._day_key(organization_id)
            )
            raw = await client.hgetall(redis_key)
            if not raw:
                return UsageBucket(by_path={})

            by_path = {
                k.removeprefix("path:"): int(v)
                for k, v in raw.items()
                if k.startswith("path:")
            }
            return UsageBucket(
                total_requests=int(raw.get("total_requests", 0)),
                error_requests=int(raw.get("error_requests", 0)),
                total_latency_ms=float(raw.get("total_latency_ms", 0.0)),
                by_path=by_path,
            )
        except Exception as exc:
            logger.debug(f"Public API usage read skipped: {exc}")
            return UsageBucket(by_path={})


def _normalize_path(path: str) -> str:
    parts = []
    for segment in path.split("/"):
        if segment.isdigit() or (len(segment) == 32 and segment.isalnum()):
            parts.append(":id")
        else:
            parts.append(segment)
    return "/".join(parts)


_public_api_usage_tracker = PublicApiUsageTracker()


def get_public_api_usage_tracker() -> PublicApiUsageTracker:
    return _public_api_usage_tracker
