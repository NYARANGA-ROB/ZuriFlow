from __future__ import annotations

from api.services.call_routing.config import CallRoutingOrgConfig, destination_for_action
from api.services.call_routing.i18n import voice_prompt_for_destination
from api.services.call_routing.types import CallRoutingPlan, RoutingDestination
from api.services.kenyan_intent.types import RouteAction, RouteDecision


class CallRoutingEngine:
    """Map detected business intents to call routing destinations."""

    def plan(
        self,
        route: RouteDecision,
        *,
        org_config: CallRoutingOrgConfig,
        language: str = "mixed",
    ) -> CallRoutingPlan | None:
        if route.action == RouteAction.CONTINUE:
            return None

        destination, base_queue = destination_for_action(route.action)
        if destination == RoutingDestination.AI_AGENT:
            return None

        queue_name = self._resolve_queue(
            base_queue,
            language=language or org_config.default_language,
            org_config=org_config,
        )

        return CallRoutingPlan(
            destination=destination,
            queue_name=queue_name,
            priority=route.priority,
            reason=route.reason,
            intent=route.intent.value,
            confidence=route.confidence,
            language=language,
            slots=dict(route.slots),
            voice_prompt=voice_prompt_for_destination(
                destination,
                language=language,
                queue_name=queue_name,
            ),
            metadata=dict(route.metadata),
        )

    @staticmethod
    def _resolve_queue(
        base_queue: str,
        *,
        language: str,
        org_config: CallRoutingOrgConfig,
    ) -> str:
        if not base_queue:
            return ""
        lang_map = org_config.language_queues.get(language) or org_config.language_queues.get(
            "mixed", {}
        )
        return lang_map.get(base_queue, base_queue)
