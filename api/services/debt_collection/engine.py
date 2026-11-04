"""Debt collection workflow engine — orchestrates negotiation, installments, escalation."""

from __future__ import annotations

import uuid
from typing import Any

from api.constants import CRM_ENABLED, DEBT_COLLECTION_ENABLED
from api.services.debt_collection.analytics import (
    track_debt_escalation_risk,
    track_installment_scheduled,
    track_negotiation_offer,
    track_payment_commitment,
    track_repayment_collected,
)
from api.services.debt_collection.compliance.service import get_compliance_guardrail_service
from api.services.debt_collection.escalation import get_debt_escalation_rules
from api.services.debt_collection.installments import get_installment_scheduler
from api.services.debt_collection.negotiation import get_payment_negotiation_engine
from api.services.debt_collection.prompts import INTERRUPTION_ACK
from api.services.debt_collection.template import KENYA_DEBT_COLLECTION
from api.services.debt_collection.types import (
    CommitmentStatus,
    DebtAccount,
    DebtCollectionSession,
    NegotiationOutcome,
)
from api.services.vertical_workflows.engine import get_vertical_workflow_engine
from api.services.vertical_workflows.registry import get_vertical_workflow_registry
from api.services.vertical_workflows.schema import WorkflowEvent, WorkflowEventType
from api.services.voice_analytics.integration import (
    track_call_started,
    track_customer_sentiment,
    track_interruption,
)


class DebtCollectionWorkflowEngine:
    """Kenyan debt collection AI workflow orchestrator."""

    TEMPLATE_ID = "kenya_debt_collection"

    def __init__(self) -> None:
        self._sessions: dict[str, DebtCollectionSession] = {}
        self._negotiation = get_payment_negotiation_engine()
        self._scheduler = get_installment_scheduler()
        self._escalation = get_debt_escalation_rules()
        self._compliance = get_compliance_guardrail_service()
        self._vertical = get_vertical_workflow_engine()

    @property
    def enabled(self) -> bool:
        return DEBT_COLLECTION_ENABLED

    def _ensure_template_registered(self) -> None:
        registry = get_vertical_workflow_registry()
        if registry.get(self.TEMPLATE_ID) is None:
            registry.register(KENYA_DEBT_COLLECTION)

    async def start(
        self,
        *,
        organization_id: int,
        account: DebtAccount,
        workflow_run_id: int | None = None,
        locale: str = "mixed",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_template_registered()
        sid = session_id or str(uuid.uuid4())
        session = DebtCollectionSession(
            session_id=sid,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            account=account,
            locale=locale,
        )
        self._sessions[sid] = session

        await self._sync_crm_on_start(session)

        vertical = await self._vertical.start(
            template_id=self.TEMPLATE_ID,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            locale=locale,
            initial_variables={
                "phone_e164": account.phone_e164,
                "customer_name": account.customer_name,
                "outstanding_balance": account.outstanding_balance,
                "account_id": account.account_id,
                "days_past_due": account.days_past_due,
            },
        )
        session.vertical_instance_id = vertical.instance_id

        track_call_started(
            organization_id=organization_id,
            session_id=sid,
            workflow_run_id=workflow_run_id or 0,
            language=locale,
            industry="debt_collection",
        )

        offer = self._negotiation.open_negotiation(session)
        track_negotiation_offer(
            organization_id=organization_id,
            session_id=sid,
            workflow_run_id=workflow_run_id or 0,
            offered_amount=offer.offered_amount,
            term_months=offer.term_months,
            round_number=session.negotiation_rounds,
            language=locale,
        )

        return await self._finalize_response(session, vertical.prompt)

    async def handle_transcript(
        self,
        session_id: str,
        text: str,
        *,
        is_final: bool = True,
        interrupted: bool = False,
    ) -> dict[str, Any]:
        session = self._require(session_id)
        if interrupted:
            session.interruption_count += 1
            track_interruption(
                organization_id=session.organization_id,
                session_id=session_id,
                workflow_run_id=session.workflow_run_id or 0,
                interrupt_count=session.interruption_count,
                language=session.locale,
            )
            ack = INTERRUPTION_ACK.get(session.locale, INTERRUPTION_ACK["mixed"])
            return {"session_id": session_id, "interruption_ack": ack, "prompt": ack}

        if is_final and text.strip():
            track_customer_sentiment(
                organization_id=session.organization_id,
                text=text,
                session_id=session_id,
                workflow_run_id=session.workflow_run_id or 0,
                language=session.locale,
            )
            await self._reliability_append_transcript(session, text)

        inbound = await self._compliance.moderate_inbound(session, text)

        decision = self._compliance.assess_escalation(
            session,
            transcript=text,
            inbound=inbound,
        )
        if decision.risk.value != "low":
            track_debt_escalation_risk(
                organization_id=session.organization_id,
                session_id=session_id,
                workflow_run_id=session.workflow_run_id or 0,
                risk=decision.risk.value,
                reason=decision.reason,
                frustration_score=session.frustration_score,
                language=session.locale,
            )

        payload: dict[str, Any] = {
            "transcript": text,
            "interrupted": interrupted,
            "escalation_risk": decision.risk.value,
        }
        if decision.should_escalate:
            payload["intent"] = "escalation"
            await self._record_crm_escalation(session, decision.reason, decision.risk.value)
            await self._trigger_human_escalation(
                session,
                decision.reason,
                decision.risk.value,
                queue=decision.queue,
            )

        result = await self._vertical.process_event(
            session.vertical_instance_id,
            WorkflowEvent(WorkflowEventType.TRANSCRIPT, payload),
        )
        await self._persist_session(session)
        return await self._finalize_response(session, result.prompt, result=result)

    async def negotiate(
        self,
        session_id: str,
        *,
        customer_offer_amount: float | None = None,
        accept: bool = False,
    ) -> dict[str, Any]:
        session = self._require(session_id)
        if not session.account:
            raise ValueError("account_required")

        if customer_offer_amount is not None:
            offer = self._negotiation.evaluate_customer_offer(session, customer_offer_amount)
            session.variables["customer_offer_amount"] = customer_offer_amount
            session.variables["negotiation_outcome"] = session.outcome.value
            message = self._negotiation.format_offer_message(
                offer, session.account, session.locale
            )
            track_negotiation_offer(
                organization_id=session.organization_id,
                session_id=session_id,
                workflow_run_id=session.workflow_run_id or 0,
                offered_amount=offer.offered_amount,
                term_months=offer.term_months,
                round_number=session.negotiation_rounds,
                acceptable=offer.acceptable,
                language=session.locale,
            )
        elif accept and session.current_offer:
            outcome = self._negotiation.record_acceptance(session)
            session.variables["negotiation_outcome"] = outcome.value
            if outcome == NegotiationOutcome.INSTALLMENT_PLAN and session.current_offer:
                plan = self._scheduler.build_plan(session.account, session.current_offer)
                session.installment_plan = plan
                session.commitments = list(plan.installments)
                track_installment_scheduled(
                    organization_id=session.organization_id,
                    session_id=session_id,
                    workflow_run_id=session.workflow_run_id or 0,
                    total_amount=plan.total_amount,
                    installment_count=len(plan.installments),
                    frequency=plan.frequency,
                    language=session.locale,
                )
                for c in plan.installments:
                    track_payment_commitment(
                        organization_id=session.organization_id,
                        session_id=session_id,
                        workflow_run_id=session.workflow_run_id or 0,
                        amount=c.amount,
                        due_date=c.due_date.isoformat(),
                        status=c.status.value,
                        language=session.locale,
                    )
                message = self._scheduler.summarize_whatsapp(plan, session.locale)
            else:
                message = self._negotiation.format_offer_message(
                    session.current_offer, session.account, session.locale
                )
        else:
            offer = self._negotiation.open_negotiation(session)
            message = self._negotiation.format_offer_message(
                offer, session.account, session.locale
            )

        result = await self._vertical.process_event(
            session.vertical_instance_id,
            WorkflowEvent(
                WorkflowEventType.MANUAL,
                {
                    "step_id": "negotiation",
                    "negotiation_outcome": session.variables.get("negotiation_outcome"),
                    "customer_offer_amount": customer_offer_amount or 0,
                },
            ),
        )
        await self._persist_session(session)
        return await self._finalize_response(session, message or result.prompt, result=result)

    async def approve_installment_plan(self, session_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        if not session.installment_plan:
            raise ValueError("no_installment_plan")
        plan = self._scheduler.approve_plan(session.installment_plan)
        session.installment_plan = plan
        session.variables["installment_plan_approved"] = True
        first = plan.installments[0] if plan.installments else None
        if first:
            session.variables["payment_amount"] = first.amount

        result = await self._vertical.process_event(
            session.vertical_instance_id,
            WorkflowEvent(
                WorkflowEventType.MANUAL,
                {"step_id": "installment", "installment_plan_approved": True},
            ),
        )
        await self._persist_session(session)
        body = self._scheduler.summarize_whatsapp(plan, session.locale)
        return await self._finalize_response(session, body, result=result)

    async def record_payment(
        self,
        session_id: str,
        *,
        status: str,
        amount: float | None = None,
        receipt: str = "",
    ) -> dict[str, Any]:
        session = self._require(session_id)
        session.variables["payment_status"] = status
        if amount is not None:
            session.variables["payment_amount"] = amount
        if status == "failed":
            session.variables["payment_failures"] = int(
                session.variables.get("payment_failures", 0)
            ) + 1

        if status == "success" and amount:
            track_repayment_collected(
                organization_id=session.organization_id,
                session_id=session_id,
                workflow_run_id=session.workflow_run_id or 0,
                amount=amount,
                receipt=receipt,
                language=session.locale,
            )
            await self._record_crm_payment(session, amount=amount, receipt=receipt)
            for c in session.commitments:
                if c.status in (CommitmentStatus.PROPOSED, CommitmentStatus.ACCEPTED):
                    c.status = CommitmentStatus.FULFILLED
                    track_payment_commitment(
                        organization_id=session.organization_id,
                        session_id=session_id,
                        workflow_run_id=session.workflow_run_id or 0,
                        amount=c.amount,
                        due_date=c.due_date.isoformat(),
                        status="fulfilled",
                        language=session.locale,
                    )
                    break

        result = await self._vertical.process_event(
            session.vertical_instance_id,
            WorkflowEvent(
                WorkflowEventType.PAYMENT_STATUS,
                {"payment_status": status, "amount": amount, "receipt": receipt},
            ),
        )
        await self._persist_session(session)
        return await self._finalize_response(session, result.prompt, result=result)

    def get_session(self, session_id: str) -> DebtCollectionSession | None:
        return self._sessions.get(session_id)

    def _require(self, session_id: str) -> DebtCollectionSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"debt collection session not found: {session_id}")
        return session

    async def _sync_crm_on_start(self, session: DebtCollectionSession) -> None:
        if not CRM_ENABLED or not session.account:
            return
        try:
            from api.services.crm.service import get_customer_service

            svc = get_customer_service()
            if not svc.enabled:
                return
            profile = await svc.sync_from_debt_collection(
                organization_id=session.organization_id,
                phone_e164=session.account.phone_e164,
                full_name=session.account.customer_name,
                account_reference=session.account.account_id,
                outstanding_balance=session.account.outstanding_balance,
                days_past_due=session.account.days_past_due,
                preferred_locale=session.locale,
                workflow_run_id=session.workflow_run_id,
            )
            session.variables["crm_customer_id"] = profile.id
            if profile.debt_accounts:
                session.variables["crm_debt_account_id"] = profile.debt_accounts[0]["id"]
        except Exception:
            pass

    async def _record_crm_payment(
        self,
        session: DebtCollectionSession,
        *,
        amount: float,
        receipt: str,
    ) -> None:
        customer_id = session.variables.get("crm_customer_id")
        if not CRM_ENABLED or not customer_id:
            return
        try:
            from api.services.crm.service import get_customer_service

            svc = get_customer_service()
            await svc.record_payment(
                int(customer_id),
                organization_id=session.organization_id,
                amount=amount,
                payment_method="mpesa",
                status="success",
                debt_account_id=session.variables.get("crm_debt_account_id"),
                workflow_run_id=session.workflow_run_id,
                receipt_reference=receipt or None,
            )
        except Exception:
            pass

    async def _trigger_human_escalation(
        self,
        session: DebtCollectionSession,
        reason: str,
        risk_level: str,
        *,
        queue: str = "collections_supervisor",
    ) -> None:
        try:
            from api.constants import HUMAN_ESCALATION_ENABLED
            if not HUMAN_ESCALATION_ENABLED:
                return
            from api.services.human_escalation.escalation_manager import get_human_escalation_manager

            manager = get_human_escalation_manager()
            account = session.account
            priority = (
                85
                if risk_level == "critical"
                else 70
                if risk_level == "high"
                else 55
            )
            await manager.escalate_from_voice_session(
                session_id=session.session_id,
                organization_id=session.organization_id,
                reason=reason,
                intent="escalation",
                language=session.locale,
                workflow_run_id=session.workflow_run_id or 0,
                phone_e164=account.phone_e164 if account else "",
                customer_name=account.customer_name if account else "",
                queue_name=queue,
                priority=priority,
                risk_level=risk_level,
            )
        except Exception:
            pass

    async def _record_crm_escalation(
        self,
        session: DebtCollectionSession,
        reason: str,
        risk_level: str,
    ) -> None:
        customer_id = session.variables.get("crm_customer_id")
        if not CRM_ENABLED or not customer_id:
            return
        try:
            from api.services.crm.service import get_customer_service

            svc = get_customer_service()
            await svc.record_escalation(
                int(customer_id),
                organization_id=session.organization_id,
                reason=reason,
                risk_level=risk_level,
                workflow_run_id=session.workflow_run_id,
                session_id=session.session_id,
            )
        except Exception:
            pass

    async def _persist_session(self, session: DebtCollectionSession) -> None:
        await self._reliability_checkpoint(session)
        if not session.workflow_run_id:
            return
        try:
            from api.db import db_client

            run = await db_client.get_workflow_run_by_id(session.workflow_run_id)
            if not run:
                return
            gathered = dict(run.gathered_context or {})
            gathered["debt_collection"] = session.to_dict()
            await db_client.update_workflow_run(
                run_id=session.workflow_run_id,
                gathered_context=gathered,
            )
        except Exception:
            pass

    async def _reliability_append_transcript(
        self, session: DebtCollectionSession, text: str
    ) -> None:
        try:
            from api.constants import CALL_RELIABILITY_ENABLED

            if not CALL_RELIABILITY_ENABLED:
                return
            from api.services.call_reliability.service import get_call_reliability_service
            from api.services.call_reliability.types import ReliabilityEventType

            await get_call_reliability_service().record_event(
                ReliabilityEventType.TRANSCRIPT,
                organization_id=session.organization_id,
                session_id=session.session_id,
                workflow_run_id=session.workflow_run_id or 0,
                payload={"text": text, "locale": session.locale},
                idempotency_key=f"transcript:{session.session_id}:{hash(text) % 10_000_000}",
            )
        except Exception:
            pass

    async def _reliability_checkpoint(self, session: DebtCollectionSession) -> None:
        try:
            from api.constants import CALL_RELIABILITY_ENABLED

            if not CALL_RELIABILITY_ENABLED:
                return
            from api.services.call_reliability.service import get_call_reliability_service

            await get_call_reliability_service().save_ws_checkpoint(
                session_id=session.session_id,
                organization_id=session.organization_id,
                workflow_run_id=session.workflow_run_id or 0,
                state=session.to_dict(),
            )
        except Exception:
            pass

    async def _finalize_response(
        self,
        session: DebtCollectionSession,
        prompt: str,
        *,
        result: Any = None,
    ) -> dict[str, Any]:
        outbound = await self._compliance.moderate_outbound(session, prompt)
        if outbound.violations:
            post_outbound = self._compliance.assess_escalation(
                session,
                outbound=outbound,
            )
            if post_outbound.should_escalate and post_outbound.risk.value != session.escalation_risk.value:
                track_debt_escalation_risk(
                    organization_id=session.organization_id,
                    session_id=session.session_id,
                    workflow_run_id=session.workflow_run_id or 0,
                    risk=post_outbound.risk.value,
                    reason=post_outbound.reason,
                    frustration_score=session.frustration_score,
                    language=session.locale,
                )
                await self._record_crm_escalation(
                    session, post_outbound.reason, post_outbound.risk.value
                )
                await self._trigger_human_escalation(
                    session,
                    post_outbound.reason,
                    post_outbound.risk.value,
                    queue=post_outbound.queue,
                )
        return self._response(session, outbound.text, result=result, compliance=outbound)

    def _response(
        self,
        session: DebtCollectionSession,
        prompt: str,
        *,
        result: Any = None,
        compliance: Any = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "session_id": session.session_id,
            "vertical_instance_id": session.vertical_instance_id,
            "prompt": prompt,
            "locale": session.locale,
            "current_step_id": result.current_step_id if result else session.variables.get("current_step_id", "greeting"),
            "negotiation_outcome": session.outcome.value,
            "escalation_risk": session.escalation_risk.value,
            "commitments": [c.to_dict() for c in session.commitments],
            "installment_plan": (
                session.installment_plan.to_dict() if session.installment_plan else None
            ),
            "variables": dict(session.variables),
        }
        if result:
            out["status"] = result.status.value
            out["actions_taken"] = result.actions_taken
            out["escalated"] = result.escalated
            out["payment_requested"] = result.payment_requested
        if compliance is not None:
            out["compliance"] = {
                "filtered": compliance.filtered,
                "used_fallback": compliance.used_fallback,
                "violations": [v.to_dict() for v in compliance.violations],
            }
        return out


_engine: DebtCollectionWorkflowEngine | None = None


def get_debt_collection_engine() -> DebtCollectionWorkflowEngine:
    global _engine
    if _engine is None:
        _engine = DebtCollectionWorkflowEngine()
    return _engine
