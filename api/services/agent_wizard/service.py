"""Session lifecycle for the agent setup wizard."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from api.db import db_client
from api.db.models import AgentSetupSessionModel, UserModel
from api.services.agent_wizard.engine import get_agent_wizard_engine
from api.services.agent_wizard.schema import (
    AgentWizardConfig,
    BusinessHoursConfig,
    CrmConfig,
    EscalationConfig,
    IndustrySelection,
    LocaleConfig,
    PaymentsConfig,
    PersonalityConfig,
    PhoneConfig,
    VoiceConfig,
    WorkflowSelection,
)
from api.services.agent_wizard.state_machine import (
    WizardStep,
    can_transition,
    infer_step_from_config,
    next_step,
    previous_step,
    progress_percent,
)
from api.services.agent_wizard.validation import validate_step


class AgentWizardService:
    async def start_session(self, user: UserModel) -> AgentSetupSessionModel:
        org_id = user.selected_organization_id
        if org_id is None:
            raise HTTPException(status_code=400, detail="No organization selected")

        existing = await db_client.get_active_agent_setup_session(
            organization_id=org_id,
            user_id=user.id,
        )
        if existing is not None:
            return existing

        return await db_client.create_agent_setup_session(
            session_uuid=str(uuid.uuid4()),
            organization_id=org_id,
            user_id=user.id,
            state=WizardStep.INDUSTRY.value,
            config={},
        )

    async def get_session(
        self,
        session_uuid: str,
        user: UserModel,
    ) -> AgentSetupSessionModel:
        session = await self._require_session(session_uuid, user)
        return session

    async def abandon_session(self, session_uuid: str, user: UserModel) -> None:
        session = await self._require_session(session_uuid, user)
        await db_client.update_agent_setup_session(
            session.id,
            state=WizardStep.FAILED.value,
            error_message="abandoned",
        )

    async def save_step(
        self,
        session_uuid: str,
        user: UserModel,
        *,
        step: WizardStep,
        industry: IndustrySelection | None = None,
        workflow: WorkflowSelection | None = None,
        locale: LocaleConfig | None = None,
        payments: PaymentsConfig | None = None,
        crm: CrmConfig | None = None,
        escalation: EscalationConfig | None = None,
        voice: VoiceConfig | None = None,
        personality: PersonalityConfig | None = None,
        business_hours: BusinessHoursConfig | None = None,
        phone: PhoneConfig | None = None,
    ) -> dict[str, Any]:
        session = await self._require_session(session_uuid, user)
        config = AgentWizardConfig.from_storage(session.config or {})

        if industry is not None:
            from api.services.agent_wizard.industries import get_industry_option

            opt = get_industry_option(industry.industry_id)
            if opt and not industry.template_id and opt.recommended_template_id:
                industry = industry.model_copy(
                    update={
                        "template_id": opt.recommended_template_id,
                        "template_source": "vertical",
                    }
                )
            config.industry = industry
        if workflow is not None:
            config.workflow = workflow
        if locale is not None:
            config.locale = locale
        if payments is not None:
            config.payments = payments
        if crm is not None:
            config.crm = crm
        if escalation is not None:
            config.escalation = escalation
        if voice is not None:
            config.voice = voice
        if personality is not None:
            config.personality = personality
        if business_hours is not None:
            config.business_hours = business_hours
        if phone is not None:
            config.phone = phone

        validation = validate_step(step, config)
        if not validation.valid:
            raise HTTPException(status_code=400, detail={"errors": validation.errors})

        target_state = step.value
        current = WizardStep(session.state)
        if not can_transition(current, step) and current != step:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot save step {step.value} from state {current.value}",
            )

        await db_client.update_agent_setup_session(
            session.id,
            state=target_state,
            config=config.to_storage(),
        )
        session = await db_client.get_agent_setup_session_by_uuid(session_uuid)
        assert session is not None
        return self._session_payload(session)

    async def advance(
        self,
        session_uuid: str,
        user: UserModel,
    ) -> dict[str, Any]:
        session = await self._require_session(session_uuid, user)
        current = WizardStep(session.state)
        config = AgentWizardConfig.from_storage(session.config or {})

        validation = validate_step(current, config)
        if not validation.valid:
            raise HTTPException(status_code=400, detail={"errors": validation.errors})

        nxt = next_step(current)
        if nxt is None:
            raise HTTPException(status_code=409, detail="Already at final step")

        await db_client.update_agent_setup_session(
            session.id,
            state=nxt.value,
        )
        session = await db_client.get_agent_setup_session_by_uuid(session_uuid)
        assert session is not None
        return self._session_payload(session)

    async def go_back(
        self,
        session_uuid: str,
        user: UserModel,
    ) -> dict[str, Any]:
        session = await self._require_session(session_uuid, user)
        current = WizardStep(session.state)
        prev = previous_step(current)
        if prev is None:
            raise HTTPException(status_code=409, detail="Already at first step")
        await db_client.update_agent_setup_session(
            session.id,
            state=prev.value,
        )
        session = await db_client.get_agent_setup_session_by_uuid(session_uuid)
        assert session is not None
        return self._session_payload(session)

    async def validate_current(
        self,
        session_uuid: str,
        user: UserModel,
    ) -> dict[str, Any]:
        session = await self._require_session(session_uuid, user)
        config = AgentWizardConfig.from_storage(session.config or {})
        current = WizardStep(session.state)
        result = validate_step(current, config)
        return {"valid": result.valid, "errors": result.errors, "step": current.value}

    async def deploy(
        self,
        session_uuid: str,
        user: UserModel,
    ) -> dict[str, Any]:
        session = await self._require_session(session_uuid, user)
        current = WizardStep(session.state)
        if current not in {WizardStep.REVIEW, WizardStep.PHONE}:
            config = AgentWizardConfig.from_storage(session.config or {})
            inferred = infer_step_from_config(config)
            if inferred != WizardStep.REVIEW:
                raise HTTPException(
                    status_code=400,
                    detail=f"Complete all steps before deploying (current: {current.value})",
                )

        await db_client.update_agent_setup_session(
            session.id,
            state=WizardStep.DEPLOYING.value,
        )
        engine = get_agent_wizard_engine()
        try:
            result = await engine.deploy(session, user_id=user.id)
        except Exception as exc:
            await db_client.update_agent_setup_session(
                session.id,
                state=WizardStep.FAILED.value,
                error_message=str(exc)[:500],
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        session = await db_client.get_agent_setup_session_by_uuid(session_uuid)
        assert session is not None
        payload = self._session_payload(session)
        payload["deployment"] = result
        return payload

    async def _require_session(
        self,
        session_uuid: str,
        user: UserModel,
    ) -> AgentSetupSessionModel:
        session = await db_client.get_agent_setup_session_by_uuid(session_uuid)
        if session is None:
            raise HTTPException(status_code=404, detail="Setup session not found")
        if session.user_id != user.id and not user.is_superuser:
            raise HTTPException(status_code=404, detail="Setup session not found")
        if (
            user.selected_organization_id
            and session.organization_id != user.selected_organization_id
            and not user.is_superuser
        ):
            raise HTTPException(status_code=404, detail="Setup session not found")
        return session

    @staticmethod
    def _session_payload(session: AgentSetupSessionModel) -> dict[str, Any]:
        step = WizardStep(session.state)
        config = AgentWizardConfig.from_storage(session.config or {})
        return {
            "session_uuid": session.session_uuid,
            "organization_id": session.organization_id,
            "state": session.state,
            "progress_percent": progress_percent(step),
            "config": config.model_dump(mode="json"),
            "workflow_id": session.workflow_id,
            "phone_number_id": session.phone_number_id,
            "error_message": session.error_message,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }


_service: AgentWizardService | None = None


def get_agent_wizard_service() -> AgentWizardService:
    global _service
    if _service is None:
        _service = AgentWizardService()
    return _service
