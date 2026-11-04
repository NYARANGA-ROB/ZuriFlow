"""Human escalation service — operator dashboard operations."""

from __future__ import annotations

from typing import Any

from api.constants import HUMAN_ESCALATION_ENABLED
from api.services.call_routing.config import CallRoutingOrgConfig
from api.services.human_escalation.escalation_manager import get_human_escalation_manager
from api.services.human_escalation.escalation_queues import EscalationQueueService
from api.services.human_escalation.handoff_service import CallHandoffService
from api.services.human_escalation.types import OperatorClaim


class HumanEscalationService:
    """Operator-facing escalation dashboard service."""

    def __init__(self) -> None:
        self._manager = get_human_escalation_manager()
        self._queues = EscalationQueueService()
        self._handoff = CallHandoffService()

    @property
    def enabled(self) -> bool:
        return HUMAN_ESCALATION_ENABLED

    async def _org_config(self, organization_id: int) -> CallRoutingOrgConfig:
        from api.services.call_routing.orchestrator import get_call_routing_orchestrator

        return await get_call_routing_orchestrator().load_org_config(organization_id)

    async def dashboard_summary(self, organization_id: int) -> dict[str, Any]:
        org_config = await self._org_config(organization_id)
        queue_names = list(org_config.language_queues.get("mixed", {}).values()) or ["human"]
        unique_queues = sorted(set(queue_names) | set(org_config.queues.keys()) | {"human"})
        depths = await self._queues.queue_depths(organization_id, unique_queues)
        pending = await self._queues.list_pending(organization_id, limit=100)
        return {
            "organization_id": organization_id,
            "queue_depths": depths,
            "pending_count": len(pending),
            "pending": pending[:20],
        }

    async def list_queue(
        self,
        organization_id: int,
        queue_name: str,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        items = await self._queues.list_queue(organization_id, queue_name, limit=limit)
        depth = await self._queues._queues.depth(organization_id, queue_name)  # noqa: SLF001
        return {"queue_name": queue_name, "depth": depth, "items": items}

    async def claim_next(
        self,
        organization_id: int,
        queue_name: str,
        *,
        operator_id: int,
    ) -> OperatorClaim | None:
        return await self._queues.claim_for_operator(
            organization_id,
            queue_name,
            operator_id=operator_id,
        )

    async def get_handoff(self, session_id: str) -> dict[str, Any] | None:
        handoff = await self._queues.get_handoff(session_id)
        return handoff.to_dict() if handoff else None

    async def transfer_claimed(
        self,
        session_id: str,
        *,
        destination: str | None = None,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        handoff = await self._queues.get_handoff(session_id)
        if handoff is None:
            return {"success": False, "error": "handoff_not_found"}

        org_config = await self._org_config(handoff.organization_id)
        dest = destination or org_config.escalation.transfer_destination
        if not dest:
            return {"success": False, "error": "no_transfer_destination"}

        result = await self._handoff.initiate_transfer(
            handoff,
            destination=dest,
            timeout_seconds=timeout_seconds,
        )
        return result

    async def resolve(self, session_id: str) -> bool:
        handoff = await self._queues.get_handoff(session_id)
        await self._queues.resolve(session_id)
        notify = self._manager._notify  # noqa: SLF001
        await notify.clear_pending(session_id)
        if handoff is not None:
            try:
                from api.services.platform_events.adapters import publish_escalation_resolved

                await publish_escalation_resolved(
                    organization_id=handoff.organization_id,
                    session_id=session_id,
                    phone_e164=handoff.phone_e164 or None,
                    workflow_run_id=handoff.workflow_run_id or None,
                    customer_id=handoff.customer_id,
                )
            except Exception:
                pass
        return True

    async def escalate_manual(
        self,
        *,
        session_id: str,
        organization_id: int,
        reason: str,
        operator_id: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self._manager.escalate_from_voice_session(
            session_id=session_id,
            organization_id=organization_id,
            reason=reason,
            **kwargs,
        )


_service: HumanEscalationService | None = None


def get_human_escalation_service() -> HumanEscalationService:
    global _service
    if _service is None:
        _service = HumanEscalationService()
    return _service
