"""Campaign throttling — rate limits, concurrency, and batch sizing."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from api.db import db_client
from api.enums import OrganizationConfigurationKey
from api.services.campaign.rate_limiter import rate_limiter
from api.services.voice_campaign.config import ThrottleConfig


class CampaignThrottler:
    """Per-campaign and per-org throttling for outbound dials."""

    def __init__(self) -> None:
        self._last_token_at: dict[str, float] = {}

    async def get_org_concurrency_limit(self, organization_id: int) -> int:
        try:
            config = await db_client.get_configuration(
                organization_id,
                OrganizationConfigurationKey.CONCURRENT_CALL_LIMIT.value,
            )
            if config and config.value:
                return int(config.value.get("value", 2))
        except Exception:
            pass
        return 2

    def effective_throttle(self, campaign, org_limit: int) -> ThrottleConfig:
        throttle = ThrottleConfig.from_campaign(campaign)
        throttle.max_concurrency = min(throttle.max_concurrency, org_limit)
        return throttle

    async def acquire_rate_token(
        self,
        organization_id: int,
        *,
        rate_limit_per_second: int,
    ) -> None:
        await rate_limiter.acquire_token(organization_id, rate_limit_per_second)

    async def apply_inter_call_delay(self, rate_limit_per_second: int) -> None:
        if rate_limit_per_second <= 0:
            return
        min_interval = 1.0 / rate_limit_per_second
        key = f"org:{rate_limit_per_second}"
        last = self._last_token_at.get(key, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_token_at[key] = time.monotonic()

    def compute_batch_size(
        self,
        throttle: ThrottleConfig,
        *,
        queue_depth: int,
        priority_high_count: int = 0,
    ) -> int:
        base = throttle.batch_size
        if queue_depth <= 0:
            return 0
        if priority_high_count > 0:
            base = min(base + 2, throttle.max_concurrency * 2)
        return int(min(base, max(1, queue_depth), throttle.max_concurrency * 2))

    async def throttle_context(self, campaign) -> dict[str, Any]:
        org_limit = await self.get_org_concurrency_limit(campaign.organization_id)
        throttle = self.effective_throttle(campaign, org_limit)
        return {
            "rate_limit_per_second": throttle.rate_limit_per_second,
            "max_concurrency": throttle.max_concurrency,
            "batch_size": throttle.batch_size,
            "use_priority_queue": throttle.use_priority_queue,
        }
