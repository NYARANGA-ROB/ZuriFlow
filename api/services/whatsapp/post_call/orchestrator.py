from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client
from api.services.whatsapp.config import ORG_CONFIG_KEY, WhatsAppOrgConfig
from api.services.whatsapp.conversation import WhatsAppConversationStore
from api.services.whatsapp.escalation import WhatsAppEscalationService
from api.services.whatsapp.messaging import WhatsAppMessagingService
from api.services.whatsapp.post_call.config import PostCallWorkflowConfig
from api.services.whatsapp.post_call.dispatcher import WhatsAppDispatcher
from api.services.whatsapp.post_call.escalation import PostCallEscalationEvaluator
from api.services.whatsapp.post_call.recovery import PostCallFailureRecovery
from api.services.whatsapp.post_call.summary import (
    PostCallSummaryGenerator,
    extract_customer_name,
    extract_customer_phone,
)
from api.services.whatsapp.post_call.types import (
    FollowUpAction,
    PostCallStep,
    PostCallWorkflowResult,
    StepResult,
)
from api.services.whatsapp.templates.engine import WhatsAppTemplateEngine
from api.services.whatsapp.templates.i18n import LOCALIZED_TEMPLATES


class PostCallWhatsAppOrchestrator:
    """Orchestrate post-call WhatsApp follow-up after voice calls end."""

    def __init__(
        self,
        *,
        summary_generator: PostCallSummaryGenerator | None = None,
        dispatcher: WhatsAppDispatcher | None = None,
        escalation_evaluator: PostCallEscalationEvaluator | None = None,
        escalation_service: WhatsAppEscalationService | None = None,
        recovery: PostCallFailureRecovery | None = None,
        store: WhatsAppConversationStore | None = None,
        messaging: WhatsAppMessagingService | None = None,
    ) -> None:
        self._summary = summary_generator or PostCallSummaryGenerator()
        self._messaging = messaging or WhatsAppMessagingService()
        self._dispatcher = dispatcher or WhatsAppDispatcher(messaging=self._messaging)
        self._escalation_evaluator = escalation_evaluator or PostCallEscalationEvaluator()
        self._escalation = escalation_service or WhatsAppEscalationService()
        self._recovery = recovery or PostCallFailureRecovery()
        self._store = store or WhatsAppConversationStore()

    async def run(
        self,
        workflow_run_id: int,
        *,
        resume_from_step: str | None = None,
        attempt: int = 1,
    ) -> PostCallWorkflowResult:
        workflow_run = await db_client.get_workflow_run_by_id(workflow_run_id)
        if not workflow_run:
            return PostCallWorkflowResult(
                workflow_run_id=workflow_run_id,
                organization_id=0,
                skipped=True,
                skip_reason="workflow_run_not_found",
            )

        organization_id = await db_client.get_organization_id_by_workflow_run_id(workflow_run_id)
        if organization_id is None:
            return PostCallWorkflowResult(
                workflow_run_id=workflow_run_id,
                organization_id=0,
                skipped=True,
                skip_reason="organization_not_found",
            )

        org_config = await self._load_org_config(organization_id)
        post_call_config = self._post_call_config(org_config)
        result = PostCallWorkflowResult(
            workflow_run_id=workflow_run_id,
            organization_id=organization_id,
        )

        if not org_config.enabled or not post_call_config.enabled:
            result.skipped = True
            result.skip_reason = "whatsapp_post_call_disabled"
            return result

        phone = extract_customer_phone(workflow_run)
        if not phone:
            result.skipped = True
            result.skip_reason = "customer_phone_missing"
            return result

        result.phone_e164 = phone
        customer_name = extract_customer_name(workflow_run)
        gathered = workflow_run.gathered_context or {}

        summary = self._summary.generate(
            workflow_run=workflow_run,
            config=post_call_config,
        )
        result.summary = summary
        result.steps.append(
            StepResult(step=PostCallStep.SUMMARIZE, success=True, detail=summary.to_dict())
        )

        conversation = await self._store.get_or_create(
            organization_id=organization_id,
            phone_e164=phone,
            provider=org_config.default_provider,
            workflow_run_id=workflow_run_id,
            metadata={
                "post_call_language": summary.language,
                "customer_name": customer_name,
            },
        )
        result.conversation_id = conversation.id

        follow_up = self._resolve_follow_up_action(summary, gathered, post_call_config)
        result.follow_up_action = follow_up

        should_escalate, escalation_reason = self._escalation_evaluator.should_escalate(
            summary=summary,
            gathered_context=gathered,
            config=post_call_config,
        )

        resume_step = PostCallStep(resume_from_step) if resume_from_step else None

        if post_call_config.auto_send_summary and self._should_run(PostCallStep.SEND_SUMMARY, resume_step):
            step = await self._dispatcher.send_summary(
                organization_id=organization_id,
                phone_e164=phone,
                customer_name=customer_name,
                summary=summary,
                workflow_run_id=workflow_run_id,
            )
            result.steps.append(step)
            if not step.success:
                await self._handle_failure(result, workflow_run_id, step.step, post_call_config, attempt)
                return result

        payment_url = self._resolve_payment_url(
            gathered, post_call_config, summary, workflow_run_id
        )
        if (
            post_call_config.auto_send_payment_link
            and follow_up in (FollowUpAction.PAYMENT, FollowUpAction.BOTH)
            and payment_url
            and self._should_run(PostCallStep.SEND_PAYMENT_LINK, resume_step)
        ):
            step = await self._dispatcher.send_payment_link(
                organization_id=organization_id,
                phone_e164=phone,
                customer_name=customer_name,
                summary=summary,
                payment_url=payment_url,
                workflow_run_id=workflow_run_id,
            )
            result.steps.append(step)
            if not step.success:
                await self._handle_failure(result, workflow_run_id, step.step, post_call_config, attempt)
                return result

        booking_url = self._resolve_booking_url(
            gathered, post_call_config, summary, workflow_run_id
        )
        if (
            post_call_config.auto_send_booking_link
            and follow_up in (FollowUpAction.BOOKING, FollowUpAction.BOTH)
            and booking_url
            and self._should_run(PostCallStep.SEND_BOOKING_LINK, resume_step)
        ):
            step = await self._dispatcher.send_booking_link(
                organization_id=organization_id,
                phone_e164=phone,
                customer_name=customer_name,
                summary=summary,
                booking_url=booking_url,
                workflow_run_id=workflow_run_id,
                appointment_date=str(gathered.get("appointment_date") or summary.slots.get("appointment_date") or ""),
                appointment_time=str(gathered.get("appointment_time") or summary.slots.get("appointment_time") or ""),
                location=str(gathered.get("location") or summary.slots.get("location") or ""),
            )
            result.steps.append(step)
            if not step.success:
                await self._handle_failure(result, workflow_run_id, step.step, post_call_config, attempt)
                return result

        if (
            post_call_config.auto_escalate
            and should_escalate
            and self._should_run(PostCallStep.ESCALATE, resume_step)
        ):
            escalation = await self._escalate(
                organization_id=organization_id,
                conversation_id=conversation.id,
                phone=phone,
                summary=summary,
                reason=escalation_reason,
            )
            result.steps.append(
                StepResult(
                    step=PostCallStep.ESCALATE,
                    success=bool(escalation.get("escalated")),
                    detail=escalation,
                )
            )
            result.escalated = bool(escalation.get("escalated"))
            if not escalation.get("escalated"):
                await self._handle_failure(
                    result, workflow_run_id, PostCallStep.ESCALATE, post_call_config, attempt
                )
                return result

        await self._recovery.persist_workflow_state(
            conversation_id=conversation.id,
            workflow_run_id=workflow_run_id,
            result=result,
            attempt=attempt,
        )
        await self._persist_run_outcome(workflow_run_id, result)
        logger.info(
            "Post-call WhatsApp workflow completed run_id={} conversation_id={} escalated={}",
            workflow_run_id,
            conversation.id,
            result.escalated,
        )
        return result

    async def _handle_failure(
        self,
        result: PostCallWorkflowResult,
        workflow_run_id: int,
        failed_step: PostCallStep,
        config: PostCallWorkflowConfig,
        attempt: int,
    ) -> None:
        await self._recovery.persist_workflow_state(
            conversation_id=result.conversation_id,
            workflow_run_id=workflow_run_id,
            result=result,
            attempt=attempt,
        )
        queued = await self._recovery.schedule_workflow_retry(
            workflow_run_id=workflow_run_id,
            resume_from_step=failed_step.value,
            attempt=attempt,
            max_attempts=config.max_workflow_attempts,
        )
        if not queued:
            await self._persist_run_outcome(workflow_run_id, result, failed=True)

    async def _escalate(
        self,
        *,
        organization_id: int,
        conversation_id: int,
        phone: str,
        summary: Any,
        reason: str,
    ) -> dict[str, Any]:
        templates = WhatsAppTemplateEngine(LOCALIZED_TEMPLATES.get(summary.language, {}))
        escalation = WhatsAppEscalationService(templates=templates)
        return await escalation.escalate(
            self._messaging,
            organization_id=organization_id,
            conversation_id=conversation_id,
            reason=reason,
            context=summary.text,
            customer_phone=phone,
        )

    async def _persist_run_outcome(
        self,
        workflow_run_id: int,
        result: PostCallWorkflowResult,
        *,
        failed: bool = False,
    ) -> None:
        await db_client.update_workflow_run(
            run_id=workflow_run_id,
            gathered_context={
                "whatsapp_post_call": result.to_dict(),
                "whatsapp_post_call_failed": failed,
            },
        )

    async def _load_org_config(self, organization_id: int) -> WhatsAppOrgConfig:
        row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
        return WhatsAppOrgConfig.from_dict(row.value if row else None)

    @staticmethod
    def _post_call_config(org_config: WhatsAppOrgConfig) -> PostCallWorkflowConfig:
        return org_config.post_call

    @staticmethod
    def _should_run(step: PostCallStep, resume_from: PostCallStep | None) -> bool:
        if resume_from is None:
            return True
        order = [
            PostCallStep.SUMMARIZE,
            PostCallStep.SEND_SUMMARY,
            PostCallStep.SEND_PAYMENT_LINK,
            PostCallStep.SEND_BOOKING_LINK,
            PostCallStep.ESCALATE,
        ]
        return order.index(step) >= order.index(resume_from)

    @staticmethod
    def _resolve_follow_up_action(
        summary: Any,
        gathered: dict[str, Any],
        config: PostCallWorkflowConfig,
    ) -> FollowUpAction:
        explicit = gathered.get("whatsapp_follow_up")
        if explicit in FollowUpAction._value2member_map_:
            return FollowUpAction(explicit)

        wants_payment = summary.intent == "request_payment" or bool(
            gathered.get("payment_url") or summary.slots.get("payment_url")
        )
        wants_booking = summary.intent in ("confirmation", "account_inquiry") or bool(
            gathered.get("booking_url")
            or gathered.get("appointment_date")
            or summary.slots.get("appointment_date")
        )
        if wants_payment and wants_booking:
            return FollowUpAction.BOTH
        if wants_payment and config.auto_send_payment_link:
            return FollowUpAction.PAYMENT
        if wants_booking and config.auto_send_booking_link:
            return FollowUpAction.BOOKING
        return FollowUpAction.NONE

    @staticmethod
    def _resolve_payment_url(
        gathered: dict[str, Any],
        config: PostCallWorkflowConfig,
        summary: Any,
        workflow_run_id: int,
    ) -> str | None:
        url = gathered.get("payment_url") or summary.slots.get("payment_url")
        if url:
            return str(url)
        template = config.payment_url_template
        if not template:
            return None
        reference = summary.slots.get("reference") or summary.slots.get("account_ref") or str(
            workflow_run_id
        )
        amount = summary.slots.get("amount") or gathered.get("amount") or ""
        return (
            template.replace("{{reference}}", reference)
            .replace("{{amount}}", str(amount))
            .replace("{{phone}}", str(gathered.get("phone_number") or ""))
        )

    @staticmethod
    def _resolve_booking_url(
        gathered: dict[str, Any],
        config: PostCallWorkflowConfig,
        summary: Any,
        workflow_run_id: int,
    ) -> str | None:
        url = gathered.get("booking_url") or summary.slots.get("booking_url")
        if url:
            return str(url)
        template = config.booking_url_template
        if not template:
            return None
        reference = summary.slots.get("reference") or str(workflow_run_id)
        return template.replace("{{reference}}", reference)
