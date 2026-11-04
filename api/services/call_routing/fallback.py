from __future__ import annotations

from api.services.call_routing.config import CallRoutingOrgConfig, FallbackConfig
from api.services.call_routing.i18n import callback_offer, voice_prompt_for_destination
from api.services.call_routing.types import (
    CallRoutingPlan,
    CallRoutingResult,
    FallbackStrategy,
    RoutingDestination,
    RoutingStatus,
)


class CallRoutingFallbackHandler:
    """Decide fallback behavior when routing cannot complete."""

    def handle_queue_full(
        self,
        plan: CallRoutingPlan,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> CallRoutingResult:
        return self._apply_strategy(
            org_config.fallback,
            plan=plan,
            reason="queue_full",
        )

    def handle_low_confidence(
        self,
        plan: CallRoutingPlan | None,
        *,
        org_config: CallRoutingOrgConfig,
        confidence: float,
    ) -> CallRoutingResult:
        if confidence >= org_config.fallback.low_confidence_threshold:
            return CallRoutingResult(
                status=RoutingStatus.PENDING,
                plan=plan,
                voice_prompt="",
            )
        return self._apply_strategy(
            org_config.fallback,
            plan=plan,
            reason="low_confidence",
        )

    def handle_transfer_failed(
        self,
        plan: CallRoutingPlan,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> CallRoutingResult:
        strategy = FallbackStrategy.RETRY_QUEUE
        if org_config.fallback.max_queue_retries <= 0:
            strategy = FallbackStrategy(org_config.fallback.strategy)
        return self._build_result(strategy, plan=plan, reason="transfer_failed")

    def handle_queue_timeout(
        self,
        plan: CallRoutingPlan,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> CallRoutingResult:
        if org_config.fallback.offer_callback:
            return CallRoutingResult(
                status=RoutingStatus.FALLBACK,
                plan=plan,
                fallback_strategy=FallbackStrategy.OFFER_CALLBACK,
                voice_prompt=callback_offer(plan.language),
                metadata={"reason": "queue_timeout"},
            )
        return self._apply_strategy(
            org_config.fallback,
            plan=plan,
            reason="queue_timeout",
        )

    def _apply_strategy(
        self,
        fallback: FallbackConfig,
        *,
        plan: CallRoutingPlan | None,
        reason: str,
    ) -> CallRoutingResult:
        try:
            strategy = FallbackStrategy(fallback.strategy)
        except ValueError:
            strategy = FallbackStrategy.CONTINUE_AI
        return self._build_result(strategy, plan=plan, reason=reason)

    def _build_result(
        self,
        strategy: FallbackStrategy,
        *,
        plan: CallRoutingPlan | None,
        reason: str,
    ) -> CallRoutingResult:
        language = plan.language if plan else "mixed"
        if strategy == FallbackStrategy.CONTINUE_AI:
            prompt = voice_prompt_for_destination(
                RoutingDestination.FALLBACK_AI,
                language=language,
            )
            return CallRoutingResult(
                status=RoutingStatus.FALLBACK,
                plan=plan,
                fallback_strategy=strategy,
                voice_prompt=prompt,
                metadata={"reason": reason},
            )
        if strategy == FallbackStrategy.OFFER_CALLBACK:
            return CallRoutingResult(
                status=RoutingStatus.FALLBACK,
                plan=plan,
                fallback_strategy=strategy,
                voice_prompt=callback_offer(language),
                metadata={"reason": reason},
            )
        if strategy == FallbackStrategy.RETRY_QUEUE:
            return CallRoutingResult(
                status=RoutingStatus.QUEUED,
                plan=plan,
                fallback_strategy=strategy,
                voice_prompt=plan.voice_prompt if plan else "",
                metadata={"reason": reason, "retry": True},
            )
        return CallRoutingResult(
            status=RoutingStatus.FALLBACK,
            plan=plan,
            fallback_strategy=strategy,
            voice_prompt="",
            metadata={"reason": reason},
        )
