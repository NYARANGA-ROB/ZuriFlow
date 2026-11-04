"""Call handoff service — execute telephony transfers to human agents."""

from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger

from api.services.human_escalation.types import HandoffPackage
from api.services.telephony.call_transfer_manager import get_call_transfer_manager
from api.services.telephony.transfer_event_protocol import TransferContext


class CallHandoffService:
    """Transfer active voice calls to human operators."""

    async def initiate_transfer(
        self,
        handoff: HandoffPackage,
        *,
        destination: str,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        if not handoff.workflow_run_id:
            return {"success": False, "error": "missing_workflow_run_id"}
        if not handoff.call_sid:
            return {"success": False, "error": "missing_call_sid"}

        try:
            from api.db import db_client
            from api.services.telephony.factory import get_telephony_provider_for_run

            run = await db_client.get_workflow_run_by_id(handoff.workflow_run_id)
            if not run:
                return {"success": False, "error": "workflow_run_not_found"}

            organization_id = handoff.organization_id
            provider = await get_telephony_provider_for_run(run, organization_id)
            if not provider.supports_transfers():
                return {"success": False, "error": "provider_does_not_support_transfer"}

            transfer_id = str(uuid.uuid4())
            conference_name = f"escalation-{handoff.call_sid}"

            transfer_context = TransferContext(
                transfer_id=transfer_id,
                call_sid=None,
                target_number=destination,
                tool_uuid="human_escalation",
                original_call_sid=handoff.call_sid,
                conference_name=conference_name,
                initiated_at=time.time(),
                workflow_run_id=handoff.workflow_run_id,
            )

            manager = await get_call_transfer_manager()
            await manager.store_transfer_context(transfer_context, ttl=600)

            result = await provider.transfer_call(
                destination=destination,
                transfer_id=transfer_id,
                conference_name=conference_name,
                timeout=timeout_seconds,
            )

            transfer_context.call_sid = result.get("call_sid")
            await manager.store_transfer_context(transfer_context, ttl=600)

            logger.info(
                "human handoff transfer initiated session={} dest={}",
                handoff.session_id,
                destination,
            )
            return {
                "success": True,
                "transfer_id": transfer_id,
                "transfer_call_sid": result.get("call_sid"),
                "destination": destination,
            }
        except Exception as exc:
            logger.exception("human handoff transfer failed session={}", handoff.session_id)
            return {"success": False, "error": str(exc)}

    async def wait_for_completion(
        self,
        transfer_id: str,
        *,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        try:
            manager = await get_call_transfer_manager()
            event = await manager.wait_for_transfer_completion(
                transfer_id,
                timeout=timeout_seconds,
            )
            if event is None:
                return {"success": False, "error": "transfer_timeout"}
            return {"success": True, **event.to_result_dict()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
