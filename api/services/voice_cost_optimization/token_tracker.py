"""Per-session token and cost tracking."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from api.constants import REDIS_URL, VOICE_COST_CACHE_TTL_S
from api.services.voice_cost_optimization.config import VoiceCostConfig, DEFAULT_VOICE_COST_CONFIG
from api.services.voice_cost_optimization.types import (
    HybridResolution,
    ResponseSource,
    TokenUsageRecord,
)


def _estimate_chars_as_tokens(char_count: int) -> int:
    return max(1, char_count // 4)


class TokenTracker:
    """Track token usage and estimated spend per voice session."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        *,
        config: VoiceCostConfig | None = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or DEFAULT_VOICE_COST_CONFIG
        self._local: dict[str, TokenUsageRecord] = {}

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    def _session_key(self, session_id: str) -> str:
        return f"voice_cost:session:{session_id}"

    def _org_key(self, organization_id: int, bucket: str) -> str:
        return f"voice_cost:org:{organization_id}:{bucket}"

    def session(
        self,
        session_id: str,
        *,
        organization_id: int = 0,
        workflow_run_id: int = 0,
    ) -> TokenUsageRecord:
        if session_id not in self._local:
            self._local[session_id] = TokenUsageRecord(
                session_id=session_id,
                organization_id=organization_id,
                workflow_run_id=workflow_run_id,
            )
        return self._local[session_id]

    def record_user_turn(self, session_id: str, user_text: str) -> int:
        record = self.session(session_id)
        tokens = _estimate_chars_as_tokens(len(user_text))
        record.input_tokens += tokens
        record.estimated_cost_usd += (
            tokens / 1_000_000
        ) * self._config.input_cost_per_million
        return tokens

    def record_llm_response(
        self,
        session_id: str,
        *,
        output_text: str,
        max_output_tokens: int | None = None,
    ) -> None:
        record = self.session(session_id)
        tokens = _estimate_chars_as_tokens(len(output_text))
        if max_output_tokens is not None:
            tokens = min(tokens, max_output_tokens)
        record.output_tokens += tokens
        record.llm_calls += 1
        record.estimated_cost_usd += (
            tokens / 1_000_000
        ) * self._config.output_cost_per_million

    def record_hybrid_resolution(
        self,
        session_id: str,
        resolution: HybridResolution,
        *,
        user_text: str = "",
    ) -> None:
        record = self.session(session_id)
        if user_text:
            self.record_user_turn(session_id, user_text)

        avoided_output = 0
        if resolution.source == ResponseSource.PRERECORDED:
            record.prerecorded_hits += 1
            avoided_output = resolution.routing.max_output_tokens if resolution.routing else 256
        elif resolution.source == ResponseSource.CACHE:
            record.cache_hits += 1
            avoided_output = resolution.routing.max_output_tokens if resolution.routing else 256
        else:
            return

        record.tokens_saved += avoided_output
        record.estimated_cost_usd = max(
            0.0,
            record.estimated_cost_usd
            - (avoided_output / 1_000_000) * self._config.output_cost_per_million,
        )

    def record_tts(self, session_id: str, text: str, *, skipped: bool = False) -> None:
        record = self.session(session_id)
        chars = len(text)
        if skipped:
            record.tts_characters += 0
            return
        record.tts_characters += chars
        record.estimated_cost_usd += (
            chars / 1000.0
        ) * self._config.tts_cost_per_1k_chars

    async def persist_session(self, session_id: str) -> None:
        record = self._local.get(session_id)
        if record is None:
            return
        redis = await self._get_redis()
        payload = json.dumps(record.to_dict(), separators=(",", ":"))
        pipe = redis.pipeline()
        pipe.setex(self._session_key(session_id), VOICE_COST_CACHE_TTL_S, payload)
        if record.organization_id > 0:
            day_bucket = time.strftime("%Y%m%d")
            org_key = self._org_key(record.organization_id, day_bucket)
            pipe.hincrby(org_key, "llm_calls", record.llm_calls)
            pipe.hincrby(org_key, "cache_hits", record.cache_hits)
            pipe.hincrby(org_key, "prerecorded_hits", record.prerecorded_hits)
            pipe.hincrby(org_key, "input_tokens", record.input_tokens)
            pipe.hincrby(org_key, "output_tokens", record.output_tokens)
            pipe.hincrby(org_key, "tokens_saved", record.tokens_saved)
            pipe.hincrbyfloat(org_key, "estimated_cost_usd", record.estimated_cost_usd)
            pipe.hincrby(org_key, "sessions", 1)
            pipe.expire(org_key, VOICE_COST_CACHE_TTL_S)
        await pipe.execute()

    async def get_session_record(self, session_id: str) -> TokenUsageRecord | None:
        if session_id in self._local:
            return self._local[session_id]
        redis = await self._get_redis()
        raw = await redis.get(self._session_key(session_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return TokenUsageRecord(
            session_id=session_id,
            organization_id=int(data.get("organization_id", 0)),
            workflow_run_id=int(data.get("workflow_run_id", 0)),
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            estimated_cost_usd=float(data.get("estimated_cost_usd", 0.0)),
            llm_calls=int(data.get("llm_calls", 0)),
            tts_characters=int(data.get("tts_characters", 0)),
            cache_hits=int(data.get("cache_hits", 0)),
            prerecorded_hits=int(data.get("prerecorded_hits", 0)),
            tokens_saved=int(data.get("tokens_saved", 0)),
        )


_tracker: TokenTracker | None = None


def get_token_tracker() -> TokenTracker:
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker
