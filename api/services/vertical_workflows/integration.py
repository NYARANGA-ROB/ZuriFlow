"""Dispatch vertical workflow actions to domain integrations."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.omnichannel.types import OrchestrationAction
from api.services.vertical_workflows.schema import (
    IntegrationBindings,
    RuleAction,
    RuleActionType,
    VerticalWorkflowInstance,
    VerticalWorkflowTemplate,
)


class VerticalWorkflowIntegration:
    """Bridge vertical workflow actions to M-Pesa, WhatsApp, and call routing."""

    async def dispatch(
        self,
        action: RuleAction,
        *,
        instance: VerticalWorkflowInstance,
        template: VerticalWorkflowTemplate,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        integrations = template.integrations
        result: dict[str, Any] = {
            "action": action.action.value,
            "params": dict(action.params),
            "dispatched": False,
        }

        match action.action:
            case RuleActionType.SET_VARIABLE:
                for key, value in action.params.items():
                    instance.variables[key] = value
                result["dispatched"] = True

            case RuleActionType.ADVANCE_STEP:
                step_id = action.params.get("step_id")
                if step_id:
                    instance.current_step_id = str(step_id)
                result["dispatched"] = True
                result["step_id"] = instance.current_step_id

            case RuleActionType.END_WORKFLOW:
                from api.services.vertical_workflows.schema import WorkflowInstanceStatus

                instance.status = WorkflowInstanceStatus.COMPLETED
                result["dispatched"] = True

            case RuleActionType.ESCALATE:
                if integrations.call_routing:
                    result.update(
                        await self._escalate(instance, action.params, context)
                    )
                else:
                    instance.variables["escalated"] = True
                    instance.variables["escalation_reason"] = action.params.get(
                        "reason", "escalation"
                    )
                    result["dispatched"] = True

            case RuleActionType.REQUEST_PAYMENT:
                if integrations.mpesa:
                    result.update(
                        await self._request_payment(instance, action.params, context)
                    )
                else:
                    instance.variables["payment_requested"] = True
                    result["dispatched"] = True

            case RuleActionType.SEND_WHATSAPP:
                result.update(await self._omnichannel(OrchestrationAction.SEND_WHATSAPP, instance, action.params, context, integrations.whatsapp))

            case RuleActionType.SEND_SMS:
                result.update(await self._omnichannel(OrchestrationAction.SEND_SMS, instance, action.params, context, integrations.sms))

            case RuleActionType.START_CALL:
                result.update(await self._omnichannel(OrchestrationAction.START_CALL, instance, action.params, context, True))

            case RuleActionType.WAIT_FOR_REPLY:
                result.update(await self._omnichannel(OrchestrationAction.WAIT_FOR_REPLY, instance, action.params, context, True))

            case RuleActionType.SEND_RECEIPT:
                result.update(await self._omnichannel(OrchestrationAction.SEND_RECEIPT, instance, action.params, context, True))

            case RuleActionType.SEND_DOCUMENT:
                result.update(await self._omnichannel(OrchestrationAction.SEND_DOCUMENT, instance, action.params, context, True))

            case RuleActionType.ROUTE_QUEUE:
                if integrations.call_routing:
                    result.update(
                        await self._route_queue(instance, action.params, context)
                    )
                else:
                    instance.variables["queue"] = action.params.get("queue", "default")
                    result["dispatched"] = True

        return result

    async def _omnichannel(
        self,
        action: OrchestrationAction,
        instance: VerticalWorkflowInstance,
        params: dict[str, Any],
        context: dict[str, Any],
        enabled: bool,
    ) -> dict[str, Any]:
        if not enabled:
            return {"dispatched": False, "error": f"{action.value.lower()}_not_enabled"}
        from api.services.omnichannel.orchestrator import get_channel_orchestrator

        phone = context.get("phone_e164") or instance.variables.get("phone_e164") or params.get("phone")
        result = await get_channel_orchestrator().execute(
            organization_id=instance.organization_id,
            action=action,
            phone=str(phone) if phone else None,
            customer_id=instance.variables.get("customer_id") or params.get("customer_id"),
            body=params.get("body") or context.get("body"),
            workflow_run_id=instance.workflow_run_id,
            transaction_id=instance.variables.get("transaction_id") or params.get("transaction_id"),
            metadata={"vertical_instance_id": instance.instance_id, **params},
        )
        dispatched = result.get("status") not in {"blocked", "failed"}
        instance.variables[f"omnichannel_{action.value.lower()}"] = dispatched
        return {"dispatched": dispatched, "integration": "omnichannel", **result}

    async def _escalate(
        self,
        instance: VerticalWorkflowInstance,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from api.services.human_escalation.escalation_manager import get_human_escalation_manager

            manager = get_human_escalation_manager()
            session_id = context.get("session_id") or instance.instance_id
            phone = context.get("phone_e164") or instance.variables.get("phone_e164", "")
            reason = str(params.get("reason", "escalation"))
            queue = str(params.get("queue", "human"))
            result = await manager.escalate_from_voice_session(
                session_id=session_id,
                organization_id=instance.organization_id,
                reason=reason,
                intent=reason,
                language=str(context.get("language") or instance.locale or "mixed"),
                workflow_run_id=instance.workflow_run_id or 0,
                phone_e164=phone,
                call_sid=str(context.get("call_sid", "")),
                queue_name=queue,
                priority=int(params.get("priority", 60)),
                risk_level=str(params.get("risk_level", "high")),
            )
            instance.variables["escalated"] = True
            instance.variables["queue"] = queue
            return {"dispatched": True, "integration": "human_escalation", **result}
        except Exception as exc:
            logger.exception("vertical workflow escalation failed")
            return {"dispatched": False, "error": str(exc)}

    async def _request_payment(
        self,
        instance: VerticalWorkflowInstance,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from api.services.vertical_workflows.schema import WorkflowInstanceStatus

            amount = params.get("amount") or context.get("amount") or instance.variables.get("amount")
            phone = context.get("phone_e164") or instance.variables.get("phone_e164", "")
            instance.variables["payment_requested"] = True
            if amount is not None:
                instance.variables["amount"] = amount
            if phone:
                instance.variables["phone_e164"] = phone
            instance.status = WorkflowInstanceStatus.WAITING_PAYMENT
            return {
                "dispatched": True,
                "integration": "mpesa",
                "amount": amount,
                "phone_e164": phone,
            }
        except Exception as exc:
            logger.exception("vertical workflow payment request failed")
            return {"dispatched": False, "error": str(exc)}

    async def _send_whatsapp(
        self,
        instance: VerticalWorkflowInstance,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from api.services.whatsapp.messaging import WhatsAppMessagingService

            phone = context.get("phone_e164") or instance.variables.get("phone_e164", "")
            if not phone:
                return {"dispatched": False, "error": "missing_phone_e164"}

            body = params.get("body") or context.get("whatsapp_body") or ""
            template_name = params.get("template")
            svc = WhatsAppMessagingService()
            await svc.send_text(
                organization_id=instance.organization_id,
                phone_e164=phone,
                body=body,
                template_name=template_name,
                workflow_run_id=instance.workflow_run_id,
                metadata={"vertical_instance_id": instance.instance_id},
            )
            instance.variables["whatsapp_sent"] = True
            return {"dispatched": True, "integration": "whatsapp"}
        except Exception as exc:
            logger.exception("vertical workflow whatsapp send failed")
            return {"dispatched": False, "error": str(exc)}

    async def _route_queue(
        self,
        instance: VerticalWorkflowInstance,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from api.services.human_escalation.escalation_manager import get_human_escalation_manager

            queue = str(params.get("queue", "human"))
            manager = get_human_escalation_manager()
            session_id = context.get("session_id") or instance.instance_id
            phone = context.get("phone_e164") or instance.variables.get("phone_e164", "")
            await manager.escalate_from_voice_session(
                session_id=session_id,
                organization_id=instance.organization_id,
                reason=str(params.get("reason", "route_queue")),
                intent="support",
                language=str(context.get("language") or instance.locale or "mixed"),
                workflow_run_id=instance.workflow_run_id or 0,
                phone_e164=phone,
                queue_name=queue,
                priority=int(params.get("priority", 40)),
                risk_level="medium",
            )
            instance.variables["queue"] = queue
            instance.variables["routed"] = True
            return {"dispatched": True, "integration": "human_escalation", "queue": queue}
        except Exception as exc:
            return {"dispatched": False, "error": str(exc)}


_integration: VerticalWorkflowIntegration | None = None


def get_vertical_workflow_integration() -> VerticalWorkflowIntegration:
    global _integration
    if _integration is None:
        _integration = VerticalWorkflowIntegration()
    return _integration
