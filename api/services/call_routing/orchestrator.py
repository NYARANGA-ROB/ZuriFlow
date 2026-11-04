from __future__ import annotations

import time
from typing import Any

from loguru import logger

from api.services.call_routing.config import (
    DEFAULT_CALL_ROUTING_CONFIG,
    ORG_CONFIG_KEY,
    CallRoutingOrgConfig,
    CallRoutingRuntimeConfig,
)
from api.services.org_config_cache import routing_config_cache
from api.services.call_routing.escalation_manager import CallEscalationManager
from api.services.call_routing.fallback import CallRoutingFallbackHandler
from api.services.call_routing.queue_service import CallRoutingQueueService
from api.services.call_routing.routing_engine import CallRoutingEngine
from api.services.call_routing.types import (
    CallRoutingContext,
    CallRoutingPlan,
    CallRoutingResult,
    EscalationRequest,
    QueueEntry,
    RoutingDestination,
    RoutingStatus,
)
from api.services.kenyan_intent.types import RouteAction, RouteDecision


class CallRoutingOrchestrator:
    """Async orchestration for intent-driven call routing."""

    def __init__(
        self,
        *,
        config: CallRoutingRuntimeConfig | None = None,
        routing_engine: CallRoutingEngine | None = None,
        queue_service: CallRoutingQueueService | None = None,
        escalation_manager: CallEscalationManager | None = None,
        fallback_handler: CallRoutingFallbackHandler | None = None,
    ) -> None:
        self._config = config or DEFAULT_CALL_ROUTING_CONFIG
        self._engine = routing_engine or CallRoutingEngine()
        self._queues = queue_service or CallRoutingQueueService(
            ttl_s=self._config.queue_ttl_s
        )
        if escalation_manager is not None:
            self._escalation = escalation_manager
        else:
            from api.services.human_escalation.escalation_manager import HumanEscalationManager

            self._escalation = HumanEscalationManager()
        self._fallback = fallback_handler or CallRoutingFallbackHandler()
        self._sessions: dict[str, CallRoutingResult] = {}

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    async def load_org_config(self, organization_id: int) -> CallRoutingOrgConfig:
        cache = routing_config_cache()
        cached = cache.get(organization_id, ORG_CONFIG_KEY)
        if cached is not None:
            return cached
        try:
            from api.db import db_client

            row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
            config = CallRoutingOrgConfig.from_dict(row.value if row else None)
            cache.set(organization_id, ORG_CONFIG_KEY, config)
            return config
        except Exception:
            logger.exception("failed to load call routing config org={}", organization_id)
            return CallRoutingOrgConfig.from_dict(None)

    async def route_from_intent(
        self,
        route: RouteDecision,
        context: CallRoutingContext,
        *,
        org_config: CallRoutingOrgConfig | None = None,
    ) -> CallRoutingResult:
        if not self._config.enabled:
            return CallRoutingResult(status=RoutingStatus.PENDING)

        org = org_config or await self.load_org_config(context.organization_id)
        if not org.enabled:
            return CallRoutingResult(status=RoutingStatus.PENDING)

        if route.confidence < self._config.route_confidence_threshold:
            return self._fallback.handle_low_confidence(
                None,
                org_config=org,
                confidence=route.confidence,
            )

        plan = self._engine.plan(
            route,
            org_config=org,
            language=context.language or route.metadata.get("language", "mixed"),
        )
        if plan is None:
            return CallRoutingResult(status=RoutingStatus.PENDING)

        if plan.destination == RoutingDestination.PAYMENT_FLOW:
            result = CallRoutingResult(
                status=RoutingStatus.COMPLETED,
                plan=plan,
                voice_prompt="",
                metadata={"handoff": "payment_flow"},
            )
            self._sessions[context.session_id] = result
            return result

        if plan.destination == RoutingDestination.AI_AGENT:
            return CallRoutingResult(status=RoutingStatus.PENDING, plan=plan)

        result = await self._enqueue_or_escalate(plan, context, org_config=org)
        self._sessions[context.session_id] = result
        return result

    async def _enqueue_or_escalate(
        self,
        plan: CallRoutingPlan,
        context: CallRoutingContext,
        *,
        org_config: CallRoutingOrgConfig,
    ) -> CallRoutingResult:
        entry = QueueEntry(
            session_id=context.session_id,
            organization_id=context.organization_id,
            queue_name=plan.queue_name,
            priority=plan.priority,
            intent=plan.intent,
            language=plan.language,
            enqueued_at=time.time(),
            workflow_run_id=context.workflow_run_id,
            phone_e164=context.phone_e164,
            metadata={"reason": plan.reason, "slots": plan.slots},
        )

        enqueued, position = await self._queues.enqueue(entry, org_config=org_config)
        if not enqueued:
            return self._fallback.handle_queue_full(plan, org_config=org_config)

        escalated = False
        escalation_meta: dict[str, Any] = {}
        if plan.destination == RoutingDestination.HUMAN_QUEUE or route_is_escalation(plan):
            from api.services.human_escalation.escalation_manager import HumanEscalationManager

            priority = plan.priority
            risk = "high" if plan.intent == "escalation" else "medium"
            request = EscalationRequest(
                session_id=context.session_id,
                organization_id=context.organization_id,
                reason=plan.reason,
                intent=plan.intent,
                language=plan.language,
                workflow_run_id=context.workflow_run_id,
                phone_e164=context.phone_e164,
                call_sid=context.call_sid,
                context=plan.reason,
                queue_name=plan.queue_name,
                transfer_destination=org_config.escalation.transfer_destination,
            )
            if isinstance(self._escalation, HumanEscalationManager):
                escalation_meta = await self._escalation.escalate(
                    request,
                    org_config=org_config,
                    priority=priority,
                    risk_level=risk,
                    enqueue=False,
                )
            else:
                escalation_meta = await self._escalation.escalate(
                    request,
                    org_config=org_config,
                )
            escalated = bool(escalation_meta.get("escalated"))
            from api.services.voice_analytics.integration import track_escalation

            track_escalation(
                organization_id=context.organization_id,
                session_id=context.session_id,
                workflow_run_id=context.workflow_run_id,
                reason=plan.reason,
                intent=plan.intent,
                queue_name=plan.queue_name,
                queue_position=position,
                language=plan.language,
            )

        voice_prompt = plan.voice_prompt
        if escalated and escalation_meta.get("voice_prompt"):
            voice_prompt = escalation_meta["voice_prompt"]

        return CallRoutingResult(
            status=RoutingStatus.QUEUED if not escalated else RoutingStatus.ESCALATING,
            plan=plan,
            queue_position=position,
            voice_prompt=voice_prompt,
            escalated=escalated,
            metadata={
                "escalation": escalation_meta,
                "queue_name": plan.queue_name,
            },
        )

    async def dequeue_for_agent(
        self,
        organization_id: int,
        queue_name: str,
    ) -> QueueEntry | None:
        return await self._queues.dequeue_next(organization_id, queue_name)

    async def queue_position(self, session_id: str) -> int | None:
        return await self._queues.position(session_id)

    async def end_session(self, session_id: str) -> CallRoutingResult | None:
        await self._queues.remove(session_id)
        await self._escalation.clear_pending(session_id)
        return self._sessions.pop(session_id, None)

    def last_result(self, session_id: str) -> CallRoutingResult | None:
        return self._sessions.get(session_id)

    def consume_voice_prompt(self, session_id: str) -> str | None:
        result = self._sessions.get(session_id)
        if result is None or not result.voice_prompt:
            return None
        prompt = result.voice_prompt
        result.voice_prompt = ""
        return prompt


def route_is_escalation(plan: CallRoutingPlan) -> bool:
    return plan.destination == RoutingDestination.HUMAN_QUEUE


_orchestrator: CallRoutingOrchestrator | None = None


def get_call_routing_orchestrator() -> CallRoutingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CallRoutingOrchestrator()
    return _orchestrator
