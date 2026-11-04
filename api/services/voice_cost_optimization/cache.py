"""Redis-backed response and TTS deduplication cache."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL
from api.services.voice_cost_optimization.config import VoiceCostConfig, DEFAULT_VOICE_COST_CONFIG


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _text_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode()).hexdigest()[:32]


class ResponseCache:
    """Cache repeated assistant answers to skip LLM regeneration."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        config: VoiceCostConfig | None = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or DEFAULT_VOICE_COST_CONFIG

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    def _answer_key(self, organization_id: int, user_hash: str) -> str:
        return f"voice_cost:answer:{organization_id}:{user_hash}"

    def _tts_key(self, organization_id: int, voice_id: str, text_hash: str) -> str:
        return f"voice_cost:tts:{organization_id}:{voice_id}:{text_hash}"

    def hash_user_text(self, text: str) -> str:
        return _text_hash(text)

    def hash_response_text(self, text: str) -> str:
        return _text_hash(text)

    async def get_cached_answer(
        self,
        organization_id: int,
        user_text: str,
    ) -> str | None:
        if not self._config.response_cache_enabled:
            return None
        redis = await self._get_redis()
        key = self._answer_key(organization_id, _text_hash(user_text))
        return await redis.get(key)

    async def put_cached_answer(
        self,
        organization_id: int,
        user_text: str,
        answer_text: str,
    ) -> None:
        if not self._config.response_cache_enabled or not answer_text.strip():
            return
        redis = await self._get_redis()
        key = self._answer_key(organization_id, _text_hash(user_text))
        payload = json.dumps(
            {"text": answer_text, "stored_at": time.time()},
            separators=(",", ":"),
        )
        await redis.setex(key, self._config.cache_ttl_s, payload)

    async def get_cached_answer_parsed(
        self,
        organization_id: int,
        user_text: str,
    ) -> str | None:
        try:
            raw = await self.get_cached_answer(organization_id, user_text)
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return str(data.get("text", "")) or None
        except json.JSONDecodeError:
            return raw

    async def mark_tts_generated(
        self,
        organization_id: int,
        *,
        voice_id: str,
        text: str,
    ) -> None:
        if not self._config.tts_dedup_enabled:
            return
        redis = await self._get_redis()
        key = self._tts_key(organization_id, voice_id, _text_hash(text))
        await redis.setex(key, self._config.cache_ttl_s, "1")

    async def has_tts_cache(
        self,
        organization_id: int,
        *,
        voice_id: str,
        text: str,
    ) -> bool:
        if not self._config.tts_dedup_enabled:
            return False
        try:
            redis = await self._get_redis()
            key = self._tts_key(organization_id, voice_id, _text_hash(text))
            return bool(await redis.get(key))
        except Exception:
            return False

    async def stats(self, organization_id: int) -> dict[str, Any]:
        redis = await self._get_redis()
        answer_keys = 0
        tts_keys = 0
        async for key in redis.scan_iter(
            match=f"voice_cost:answer:{organization_id}:*", count=50
        ):
            answer_keys += 1
        async for key in redis.scan_iter(
            match=f"voice_cost:tts:{organization_id}:*", count=50
        ):
            tts_keys += 1
        return {
            "organization_id": organization_id,
            "cached_answers": answer_keys,
            "cached_tts_phrases": tts_keys,
        }


_cache: ResponseCache | None = None


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache
