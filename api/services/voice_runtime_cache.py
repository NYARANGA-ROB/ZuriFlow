"""Tenant-scoped Redis cache for non-sensitive realtime voice metadata.

Never store phone numbers, recordings, transcripts, payment data, or API secrets.
Every key includes organization_id so entries cannot leak across tenants.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable

import redis.asyncio as aioredis

from api.constants import REDIS_URL

_PREFIX = "voice_rt"
_DEFAULT_TTL_S = 60
_redis_client: aioredis.Redis | None = None

_FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "phone",
        "phone_e164",
        "transcript",
        "recording",
        "password",
        "secret",
        "api_key",
        "token",
        "mpesa",
        "receipt",
        "national_id",
        "otp",
    }
)


async def _redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _key(organization_id: int, kind: str, name: str) -> str:
    if organization_id <= 0:
        raise ValueError("organization_id is required for realtime cache keys")
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
    return f"{_PREFIX}:{organization_id}:{kind}:{digest}"


def _assert_safe_payload(payload: dict[str, Any]) -> None:
    for key in payload:
        if key.lower() in _FORBIDDEN_FIELD_NAMES:
            raise ValueError(f"Refusing to cache tenant-sensitive field {key}")


async def cache_get(organization_id: int, kind: str, name: str) -> dict[str, Any] | None:
    try:
        redis = await _redis()
        raw = await redis.get(_key(organization_id, kind, name))
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def cache_set(
    organization_id: int,
    kind: str,
    name: str,
    payload: dict[str, Any],
    *,
    ttl_s: int = _DEFAULT_TTL_S,
) -> None:
    _assert_safe_payload(payload)
    try:
        redis = await _redis()
        await redis.setex(
            _key(organization_id, kind, name),
            ttl_s,
            json.dumps(payload, separators=(",", ":"), default=str),
        )
    except Exception:
        return


async def get_or_load(
    organization_id: int,
    kind: str,
    name: str,
    loader: Callable[[], Awaitable[dict[str, Any] | None]],
    *,
    ttl_s: int = _DEFAULT_TTL_S,
) -> dict[str, Any] | None:
    cached = await cache_get(organization_id, kind, name)
    if cached is not None:
        return cached
    loaded = await loader()
    if isinstance(loaded, dict):
        await cache_set(organization_id, kind, name, loaded, ttl_s=ttl_s)
    return loaded


async def allow_ws_connect(organization_id: int, *, per_second: int = 40) -> bool:
    """Org-scoped WebSocket connect rate limit. Fail-open if Redis is down."""
    if organization_id <= 0:
        return True
    try:
        redis = await _redis()
        key = f"{_PREFIX}:{organization_id}:rl:ws_connect"
        n = await redis.incr(key)
        if n == 1:
            await redis.expire(key, 1)
        return n <= per_second
    except Exception:
        return True
