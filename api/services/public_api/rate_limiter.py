"""HTTP API rate limiting for the public API platform."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis
from loguru import logger

from api.constants import (
    ENVIRONMENT,
    PUBLIC_API_RATE_LIMIT_PER_KEY_PER_MIN,
    PUBLIC_API_RATE_LIMIT_PER_ORG_PER_MIN,
    REDIS_URL,
)
from api.enums import Environment


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after_s: float = 0.0


class PublicApiRateLimiter:
    """Sliding-window rate limiter scoped per organization and API key."""

    WINDOW_S = 60.0

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None

    async def _redis_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    async def check(
        self,
        *,
        organization_id: int,
        api_key_id: int,
        org_limit: int | None = None,
        key_limit: int | None = None,
    ) -> RateLimitResult:
        org_limit = org_limit or PUBLIC_API_RATE_LIMIT_PER_ORG_PER_MIN
        key_limit = key_limit or PUBLIC_API_RATE_LIMIT_PER_KEY_PER_MIN

        org_result = await self._acquire(
            f"public_api:rl:org:{organization_id}", org_limit
        )
        if not org_result.allowed:
            return org_result

        key_result = await self._acquire(
            f"public_api:rl:key:{api_key_id}", key_limit
        )
        return key_result

    async def _acquire(self, key: str, limit: int) -> RateLimitResult:
        now = time.time()
        window_start = now - self.WINDOW_S
        lua = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local max_requests = tonumber(ARGV[3])
        redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
        local current = redis.call('ZCARD', key)
        if current < max_requests then
            redis.call('ZADD', key, now, now)
            redis.call('EXPIRE', key, 120)
            return {1, max_requests - current - 1}
        end
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 1
        if oldest[2] then
            retry_after = math.max(1, math.ceil((tonumber(oldest[2]) + 60) - now))
        end
        return {0, 0, retry_after}
        """
        try:
            redis_client = await self._redis_client()
            result = await redis_client.eval(
                lua, 1, key, now, window_start, limit
            )
            allowed = bool(result[0])
            remaining = int(result[1]) if allowed else 0
            retry_after = float(result[2]) if not allowed else 0.0
            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                retry_after_s=retry_after,
            )
        except Exception as exc:
            logger.warning(f"Public API rate limiter error: {exc}")
            if ENVIRONMENT == Environment.PRODUCTION.value:
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    retry_after_s=5.0,
                )
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
            )


_public_api_rate_limiter = PublicApiRateLimiter()


def get_public_api_rate_limiter() -> PublicApiRateLimiter:
    return _public_api_rate_limiter
