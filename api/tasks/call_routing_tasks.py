"""ARQ tasks for async call routing (escalation retries, queue timeouts)."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.call_routing.orchestrator import get_call_routing_orchestrator
from api.services.call_routing.types import EscalationRequest


async def process_call_routing_escalation(ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Retry or complete a pending human escalation."""
    _ = ctx
    orch = get_call_routing_orchestrator()
    org_id = int(payload["organization_id"])
    org_config = await orch.load_org_config(org_id)

    from api.services.call_routing.escalation_manager import CallEscalationManager

    manager = CallEscalationManager()
    request = EscalationRequest(
        session_id=payload["session_id"],
        organization_id=org_id,
        reason=payload.get("reason", "escalation"),
        intent=payload.get("intent", "escalation"),
        language=payload.get("language", "mixed"),
        workflow_run_id=int(payload.get("workflow_run_id", 0)),
        phone_e164=payload.get("phone_e164", ""),
        call_sid=payload.get("call_sid", ""),
        context=payload.get("context", ""),
        queue_name=payload.get("queue_name", "human"),
        transfer_destination=payload.get("transfer_destination", ""),
    )
    result = await manager.escalate(request, org_config=org_config)
    logger.info(
        "call routing escalation task session={} escalated={}",
        request.session_id[:8],
        result.get("escalated"),
    )
    return result


async def process_call_routing_queue_timeout(ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply fallback when a queued caller exceeds max wait."""
    _ = ctx
    from api.services.call_routing.fallback import CallRoutingFallbackHandler
    from api.services.call_routing.types import CallRoutingPlan, RoutingDestination

    orch = get_call_routing_orchestrator()
    org_id = int(payload["organization_id"])
    org_config = await orch.load_org_config(org_id)

    plan = CallRoutingPlan(
        destination=RoutingDestination(payload.get("destination", "human_queue")),
        queue_name=payload.get("queue_name", "human"),
        priority=int(payload.get("priority", 0)),
        reason=payload.get("reason", "queue timeout"),
        intent=payload.get("intent", "unknown"),
        confidence=float(payload.get("confidence", 0.0)),
        language=payload.get("language", "mixed"),
    )
    handler = CallRoutingFallbackHandler()
    result = handler.handle_queue_timeout(plan, org_config=org_config)
    return result.to_dict()
