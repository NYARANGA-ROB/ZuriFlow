from __future__ import annotations

from api.constants import CALL_ROUTING_ENABLED
from api.services.call_routing.orchestrator import CallRoutingOrchestrator, get_call_routing_orchestrator
from api.services.call_routing.types import CallRoutingContext, CallRoutingResult
from api.services.kenyan_intent.types import RouteAction, RouteDecision


async def route_call_from_intent(
    route: RouteDecision,
    *,
    session_id: str,
    organization_id: int,
    workflow_run_id: int = 0,
    phone_e164: str = "",
    customer_name: str = "there",
    call_sid: str = "",
    language: str = "mixed",
    orchestrator: CallRoutingOrchestrator | None = None,
) -> CallRoutingResult | None:
    if not CALL_ROUTING_ENABLED:
        return None
    if route.action == RouteAction.CONTINUE:
        return None

    orch = orchestrator or get_call_routing_orchestrator()
    if not orch.enabled:
        return None

    context = CallRoutingContext(
        session_id=session_id,
        organization_id=organization_id,
        workflow_run_id=workflow_run_id,
        phone_e164=phone_e164,
        customer_name=customer_name,
        call_sid=call_sid,
        language=language or route.metadata.get("language", "mixed"),
    )
    return await orch.route_from_intent(route, context)


def call_routing_enabled_for_session(metadata: dict | None) -> bool:
    if not CALL_ROUTING_ENABLED:
        return False
    meta = metadata or {}
    if "call_routing_enabled" in meta:
        return bool(meta["call_routing_enabled"])
    return True


def system_hint_from_routing(result: CallRoutingResult | None) -> str | None:
    if result is None or not result.plan:
        return None
    if result.status.value in {"pending", "completed"} and not result.voice_prompt:
        return None
    parts = [
        f"[Call routing: {result.status.value}",
        f"destination={result.plan.destination.value}",
    ]
    if result.queue_position:
        parts.append(f"queue_position={result.queue_position}")
    if result.fallback_strategy:
        parts.append(f"fallback={result.fallback_strategy.value}")
    parts.append("]")
    hint = " ".join(parts)
    if result.plan.reason:
        hint += f" {result.plan.reason}."
    return hint
