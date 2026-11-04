"""Hybrid response engine — prerecorded, cache, then LLM."""

from __future__ import annotations

from api.services.voice_cost_optimization.cache import ResponseCache, get_response_cache
from api.services.voice_cost_optimization.config import VoiceCostConfig, DEFAULT_VOICE_COST_CONFIG
from api.services.voice_cost_optimization.prerecorded import (
    match_prerecorded,
    prerecorded_for_intent,
)
from api.services.voice_cost_optimization.routing_engine import (
    IntelligentRoutingEngine,
    get_intelligent_routing_engine,
)
from api.services.voice_cost_optimization.types import HybridResolution, ResponseSource


class HybridResponseEngine:
    """Resolve a user turn to the cheapest valid response path."""

    def __init__(
        self,
        *,
        routing: IntelligentRoutingEngine | None = None,
        cache: ResponseCache | None = None,
        config: VoiceCostConfig | None = None,
    ) -> None:
        self._routing = routing or get_intelligent_routing_engine()
        self._cache = cache or get_response_cache()
        self._config = config or DEFAULT_VOICE_COST_CONFIG

    async def resolve_turn(
        self,
        user_text: str,
        *,
        organization_id: int = 0,
        session_id: str = "",
        locale: str = "mixed",
        turn_count: int = 0,
        intent: str = "",
        intent_confidence: float = 0.0,
        voice_id: str = "",
    ) -> HybridResolution:
        if not self._config.enabled:
            routing = self._routing.classify(user_text, turn_count=turn_count)
            return HybridResolution(
                source=ResponseSource.LLM,
                routing=routing,
            )

        routing = self._routing.classify(
            user_text,
            turn_count=turn_count,
            intent=intent,
            intent_confidence=intent_confidence,
        )

        if self._config.prerecorded_enabled:
            if intent:
                phrase = prerecorded_for_intent(intent, locale=locale)
                if phrase and routing.skip_llm:
                    tts_cached = await self._cache.has_tts_cache(
                        organization_id, voice_id=voice_id, text=phrase
                    )
                    return HybridResolution(
                        source=ResponseSource.PRERECORDED,
                        text=phrase,
                        routing=routing,
                        prerecorded_key=intent,
                        tts_cached=tts_cached,
                    )
            matched = match_prerecorded(user_text, locale=locale)
            if matched:
                key, phrase = matched
                tts_cached = await self._cache.has_tts_cache(
                    organization_id, voice_id=voice_id, text=phrase
                )
                return HybridResolution(
                    source=ResponseSource.PRERECORDED,
                    text=phrase,
                    routing=routing,
                    prerecorded_key=key,
                    tts_cached=tts_cached,
                )

        if organization_id > 0:
            cached = await self._cache.get_cached_answer_parsed(
                organization_id, user_text
            )
            if cached:
                tts_cached = await self._cache.has_tts_cache(
                    organization_id, voice_id=voice_id, text=cached
                )
                return HybridResolution(
                    source=ResponseSource.CACHE,
                    text=cached,
                    routing=routing,
                    cache_key=self._cache.hash_user_text(user_text),
                    tts_cached=tts_cached,
                )

        return HybridResolution(source=ResponseSource.LLM, routing=routing)

    async def store_llm_response(
        self,
        organization_id: int,
        user_text: str,
        answer_text: str,
        *,
        voice_id: str = "",
    ) -> None:
        if organization_id <= 0 or not answer_text.strip():
            return
        await self._cache.put_cached_answer(
            organization_id, user_text, answer_text
        )
        if voice_id:
            await self._cache.mark_tts_generated(
                organization_id, voice_id=voice_id, text=answer_text
            )


_hybrid: HybridResponseEngine | None = None


def get_hybrid_response_engine() -> HybridResponseEngine:
    global _hybrid
    if _hybrid is None:
        _hybrid = HybridResponseEngine()
    return _hybrid
