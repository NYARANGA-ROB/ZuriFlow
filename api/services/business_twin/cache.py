"""Redis cache for twin metadata. Never overrides live connector results."""

from __future__ import annotations

from api.services.campaign.rate_limiter import rate_limiter

CACHE_PREFIX = "biz_twin"


def cache_key(organization_id: int, kind: str) -> str:
    return f"{CACHE_PREFIX}:{organization_id}:{kind}"


async def invalidate(organization_id: int, *kinds: str) -> None:
    try:
        redis = await rate_limiter._get_redis()
    except Exception:
        return
    for kind in kinds or ("hours", "price", "inventory", "promotions", "profile"):
        await redis.delete(cache_key(organization_id, kind))


async def claim_nonce(organization_id: int, nonce: str, ttl_s: int = 300) -> bool:
    try:
        redis = await rate_limiter._get_redis()
        key = f"{CACHE_PREFIX}:nonce:{organization_id}:{nonce}"
        return bool(await redis.set(key, "1", nx=True, ex=ttl_s))
    except Exception:
        return True


EVENT_INVALIDATIONS = {
    "INVENTORY_CHANGED": ("inventory",),
    "PRICE_CHANGED": ("price",),
    "BUSINESS_HOURS_CHANGED": ("hours",),
    "PROMOTION_STARTED": ("promotions",),
    "PROMOTION_EXPIRED": ("promotions",),
    "PAYMENT_CONFIRMED": ("payment",),
    "PAYMENT_FAILED": ("payment",),
    "BOOKING_CREATED": ("booking",),
    "BOOKING_CANCELLED": ("booking",),
    "ORDER_UPDATED": ("order",),
    "CUSTOMER_UPDATED": ("crm",),
}
