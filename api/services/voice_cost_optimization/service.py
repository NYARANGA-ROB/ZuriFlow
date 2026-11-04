"""Facade for voice cost optimization."""

from __future__ import annotations

from typing import Any

from api.constants import VOICE_COST_OPTIMIZATION_ENABLED
from api.services.voice_cost_optimization.analytics import (
    VoiceCostAnalytics,
    get_voice_cost_analytics,
)
from api.services.voice_cost_optimization.cache import ResponseCache, get_response_cache
from api.services.voice_cost_optimization.config import DEFAULT_VOICE_COST_CONFIG
from api.services.voice_cost_optimization.hybrid_engine import (
    HybridResponseEngine,
    get_hybrid_response_engine,
)
from api.services.voice_cost_optimization.prerecorded import list_prerecorded_keys
from api.services.voice_cost_optimization.routing_engine import (
    IntelligentRoutingEngine,
    get_intelligent_routing_engine,
)
from api.services.voice_cost_optimization.token_tracker import TokenTracker, get_token_tracker
from api.services.voice_cost_optimization.types import HybridResolution


class VoiceCostOptimizationService:
    """Orchestrates routing, caching, hybrid responses, tracking, and analytics."""

    def __init__(self) -> None:
        self._routing = get_intelligent_routing_engine()
        self._cache = get_response_cache()
        self._hybrid = get_hybrid_response_engine()
        self._tracker = get_token_tracker()
        self._analytics = get_voice_cost_analytics()

    @property
    def enabled(self) -> bool:
        return VOICE_COST_OPTIMIZATION_ENABLED

    async def resolve_turn(self, user_text: str, **kwargs) -> HybridResolution:
        if not self.enabled:
            routing = self._routing.classify(user_text)
            from api.services.voice_cost_optimization.types import ResponseSource

            return HybridResolution(source=ResponseSource.LLM, routing=routing)
        return await self._hybrid.resolve_turn(user_text, **kwargs)

    async def store_llm_response(self, *args, **kwargs) -> None:
        if self.enabled:
            await self._hybrid.store_llm_response(*args, **kwargs)

    def tracker(self) -> TokenTracker:
        return self._tracker

    def analytics(self) -> VoiceCostAnalytics:
        return self._analytics

    def routing(self) -> IntelligentRoutingEngine:
        return self._routing

    def cache(self) -> ResponseCache:
        return self._cache

    async def get_cost_analytics(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
    ):
        return await self._analytics.aggregate_organization(
            organization_id, from_ts=from_ts, to_ts=to_ts
        )

    def status(self) -> dict[str, Any]:
        cfg = DEFAULT_VOICE_COST_CONFIG
        return {
            "enabled": self.enabled,
            "prerecorded_enabled": cfg.prerecorded_enabled,
            "response_cache_enabled": cfg.response_cache_enabled,
            "tts_dedup_enabled": cfg.tts_dedup_enabled,
            "token_budgets": {
                "simple": cfg.simple_max_tokens,
                "standard": cfg.standard_max_tokens,
                "complex": cfg.complex_max_tokens,
            },
            "prerecorded_keys": list_prerecorded_keys(),
        }


_service: VoiceCostOptimizationService | None = None


def get_voice_cost_optimization_service() -> VoiceCostOptimizationService:
    global _service
    if _service is None:
        _service = VoiceCostOptimizationService()
    return _service
