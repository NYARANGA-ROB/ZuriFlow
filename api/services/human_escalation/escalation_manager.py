"""Human escalation manager — orchestrates queue, context, notify, and transfer."""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from api.constants import CRM_ENABLED, HUMAN_ESCALATION_ENABLED
from api.services.call_routing.config import CallRoutingOrgConfig
from api.services.call_routing.escalation_manager import CallEscalationManager
from api.services.call_routing.types import EscalationRequest
from api.services.human_escalation.context_transfer import ContextTransferSystem
from api.services.human_escalation.escalation_queues import EscalationQueueService
from api.services.human_escalation.handoff_service import CallHandoffService
from api.services.human_escalation.types import EscalationStatus, HandoffPackage


class HumanEscalationManager:
    """Full human escalation flow with context preservation and priority routing."""

    def __init__(self) -> None:
        self._context = ContextTransferSystem()
        self._queues = EscalationQueueService()
        self._handoff = CallHandoffService()
        self._notify = CallEscalationManager()

    @property
    def enabled(self) -> bool:
        return HUMAN_ESCALATION_ENABLED

    async def escalate(
        self,
        request: EscalationRequest,
        *,
        org_config: CallRoutingOrgConfig,
        priority: int = 50,
        risk_level: str = "medium",
        enqueue: bool = True,
        extra_context: str = "",
    ) -> dict[str, Any]:
        if not self.enabled:
            return await self._notify.escalate(request, org_config=org_config)

        handoff = await self._context.build_handoff(
            session_id=request.session_id,
            organization_id=request.organization_id,
            reason=request.reason,
            intent=request.intent,
            language=request.language,
            workflow_run_id=request.workflow_run_id,
            phone_e164=request.phone_e164,
            call_sid=request.call_sid,
            queue_name=request.queue_name or "human",
            priority=priority,
            risk_level=risk_level,
            extra_context=extra_context or request.context,
        )

        position = 0
        enqueued = False
        if enqueue and handoff.queue_name:
            enqueued, position = await self._queues.enqueue_with_handoff(
                handoff,
                org_config=org_config,
            )
        else:
            await self._queues.store_handoff(handoff)

        await self._record_crm_escalation(handoff)
        await self._publish_escalation_event(handoff)

        enriched_request = EscalationRequest(
            session_id=request.session_id,
            organization_id=request.organization_id,
            reason=request.reason,
            intent=request.intent,
            language=request.language,
            workflow_run_id=request.workflow_run_id,
            phone_e164=request.phone_e164,
            call_sid=request.call_sid,
            context=handoff.summary,
            queue_name=request.queue_name,
            transfer_destination=request.transfer_destination,
        )
        notify_result = await self._notify.escalate(enriched_request, org_config=org_config)

        transfer_result: dict[str, Any] | None = None
        dest = request.transfer_destination or org_config.escalation.transfer_destination
        if (
            notify_result.get("pending_transfer")
            and dest
            and handoff.call_sid
            and org_config.escalation.auto_transfer
        ):
            transfer_result = await self._handoff.initiate_transfer(
                handoff,
                destination=dest,
            )

        await self._store_escalation_status(
            request.session_id,
            status=EscalationStatus.TRANSFERRING if transfer_result and transfer_result.get("success") else EscalationStatus.QUEUED,
            handoff=handoff,
        )

        summary_sent = bool(notify_result.get("webhook_notified") or notify_result.get("whatsapp_notified"))

        return {
            **notify_result,
            "handoff": handoff.to_dict(),
            "queue_position": position if enqueued else None,
            "enqueued": enqueued,
            "summary_sent": summary_sent,
            "transfer": transfer_result,
        }

    async def escalate_from_voice_session(
        self,
        *,
        session_id: str,
        organization_id: int,
        reason: str,
        intent: str = "escalation",
        language: str = "mixed",
        workflow_run_id: int = 0,
        phone_e164: str = "",
        call_sid: str = "",
        queue_name: str = "human",
        priority: int = 50,
        risk_level: str = "medium",
        customer_name: str = "",
    ) -> dict[str, Any]:
        from api.services.call_routing.orchestrator import get_call_routing_orchestrator

        orch = get_call_routing_orchestrator()
        org_config = await orch.load_org_config(organization_id)

        request = EscalationRequest(
            session_id=session_id,
            organization_id=organization_id,
            reason=reason,
            intent=intent,
            language=language,
            workflow_run_id=workflow_run_id,
            phone_e164=phone_e164,
            call_sid=call_sid,
            queue_name=queue_name,
        )

        handoff = await self._context.build_handoff(
            session_id=session_id,
            organization_id=organization_id,
            reason=reason,
            intent=intent,
            language=language,
            workflow_run_id=workflow_run_id,
            phone_e164=phone_e164,
            customer_name=customer_name,
            call_sid=call_sid,
            queue_name=queue_name,
            priority=priority,
            risk_level=risk_level,
        )

        return await self.escalate(
            request,
            org_config=org_config,
            priority=priority,
            risk_level=risk_level,
            enqueue=True,
            extra_context=handoff.summary,
        )

    async def get_handoff(self, session_id: str) -> HandoffPackage | None:
        return await self._queues.get_handoff(session_id)

    async def _record_crm_escalation(self, handoff: HandoffPackage) -> None:
        if not CRM_ENABLED or not handoff.customer_id:
            return
        try:
            from api.services.crm.service import get_customer_service

            svc = get_customer_service()
            await svc.record_escalation(
                handoff.customer_id,
                organization_id=handoff.organization_id,
                reason=handoff.reason,
                risk_level=handoff.risk_level,
                workflow_run_id=handoff.workflow_run_id or None,
                session_id=handoff.session_id,
                metadata={"summary": handoff.summary[:500]},
            )
        except Exception:
            logger.debug("CRM escalation record skipped session={}", handoff.session_id)

    async def _publish_escalation_event(self, handoff: HandoffPackage) -> None:
        try:
            from api.services.platform_events.adapters import publish_escalation_created

            await publish_escalation_created(
                organization_id=handoff.organization_id,
                session_id=handoff.session_id,
                reason=handoff.reason,
                phone_e164=handoff.phone_e164 or None,
                workflow_run_id=handoff.workflow_run_id or None,
                customer_id=handoff.customer_id,
                risk_level=handoff.risk_level,
                queue_name=handoff.queue_name,
            )
        except Exception:
            logger.debug("platform escalation event skipped session={}", handoff.session_id)

    async def _store_escalation_status(
        self,
        session_id: str,
        *,
        status: EscalationStatus,
        handoff: HandoffPackage,
    ) -> None:
        try:
            import redis.asyncio as aioredis

            from api.constants import REDIS_URL

            redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
            await redis.setex(
                f"human_escalation:status:{session_id}",
                3600,
                json.dumps(
                    {
                        "status": status.value,
                        "updated_at": time.time(),
                        "session_id": session_id,
                    }
                ),
            )
        except Exception:
            pass


_manager: HumanEscalationManager | None = None


def get_human_escalation_manager() -> HumanEscalationManager:
    global _manager
    if _manager is None:
        _manager = HumanEscalationManager()
    return _manager
