"""Orchestrates agent deployment from wizard sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.db import db_client
from api.db.models import AgentSetupSessionModel
from api.enums import OrganizationConfigurationKey
from api.schemas.ai_model_configuration import (
    DOGRAH_DEFAULT_LANGUAGE,
    DOGRAH_DEFAULT_VOICE,
)
from api.services.agent_wizard.schema import AgentWizardConfig
from api.services.agent_wizard.validation import validate_for_deploy
from api.services.agent_wizard.workflow_builder import (
    build_workflow_configurations,
    build_workflow_definition,
)
from api.services.configuration.ai_model_configuration import (
    get_organization_ai_model_configuration_v2,
    upsert_organization_ai_model_configuration_v2,
)
from api.services.organization_preferences import upsert_organization_preferences
from api.services.template_marketplace.org_config import normalize_org_config
from api.services.user_onboarding import update_onboarding_state
from api.schemas.onboarding_state import OnboardingStateUpdate
from api.services.workflow.trigger_paths import extract_trigger_paths


class AgentWizardEngine:
    """Provision workflows, voice, telephony, and org settings from wizard config."""

    async def deploy(
        self,
        session: AgentSetupSessionModel,
        *,
        user_id: int,
    ) -> dict[str, Any]:
        config = AgentWizardConfig.from_storage(session.config or {})
        validation = validate_for_deploy(config)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))

        org_id = session.organization_id
        assert config.workflow is not None

        workflow_def = build_workflow_definition(config)
        wf_configs = build_workflow_configurations(config)

        trigger_paths = extract_trigger_paths(workflow_def) if workflow_def else []
        if trigger_paths:
            await db_client.assert_trigger_paths_available(trigger_paths=trigger_paths)

        workflow = await db_client.create_workflow(
            name=config.workflow.agent_name,
            workflow_definition=workflow_def,
            user_id=user_id,
            organization_id=org_id,
        )

        if wf_configs:
            await db_client.update_workflow(
                workflow.id,
                name=None,
                workflow_definition=None,
                template_context_variables=None,
                workflow_configurations=wf_configs,
                organization_id=org_id,
            )

        if trigger_paths:
            await db_client.sync_triggers_for_workflow(
                workflow_id=workflow.id,
                organization_id=org_id,
                trigger_paths=trigger_paths,
            )

        phone_number_id = await self._assign_phone(config, org_id, workflow.id)
        await self._apply_voice_config(config, org_id)
        await self._apply_org_preferences(config, org_id)
        await self._store_vertical_binding(config, org_id)

        await db_client.update_agent_setup_session(
            session.id,
            workflow_id=workflow.id,
            phone_number_id=phone_number_id,
            state="completed",
            completed_at=datetime.now(UTC),
            error_message=None,
        )

        await update_onboarding_state(
            user_id,
            OnboardingStateUpdate(completed_actions=["agent_wizard_deployed"]),
        )

        logger.info(
            "Agent wizard deployed session={} workflow={} org={}",
            session.session_uuid,
            workflow.id,
            org_id,
        )
        return {
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "phone_number_id": phone_number_id,
            "session_uuid": session.session_uuid,
        }

    async def _assign_phone(
        self,
        config: AgentWizardConfig,
        org_id: int,
        workflow_id: int,
    ) -> int | None:
        phone = config.phone
        if phone is None or phone.skip_assignment:
            return None
        assert phone.telephony_configuration_id is not None
        assert phone.address is not None

        configs = await db_client.list_telephony_configurations(org_id)
        valid_ids = {c.id for c in configs}
        if phone.telephony_configuration_id not in valid_ids:
            raise ValueError("Telephony configuration not found for this organization")

        row = await db_client.create_phone_number(
            organization_id=org_id,
            telephony_configuration_id=phone.telephony_configuration_id,
            address=phone.address,
            country_code=phone.country_code,
            label=phone.label or config.workflow.agent_name if config.workflow else None,
            inbound_workflow_id=workflow_id if config.workflow and config.workflow.call_direction == "inbound" else None,
            is_default_caller_id=config.workflow.call_direction == "outbound" if config.workflow else False,
            extra_metadata={"source": "agent_wizard"},
        )
        return row.id

    async def _apply_voice_config(self, config: AgentWizardConfig, org_id: int) -> None:
        if config.voice is None:
            return
        existing = await get_organization_ai_model_configuration_v2(org_id)
        if existing is None or existing.mode != "dograh" or existing.dograh is None:
            return
        existing.dograh.voice = config.voice.voice_id or DOGRAH_DEFAULT_VOICE
        existing.dograh.speed = config.voice.speed
        existing.dograh.language = config.voice.language or DOGRAH_DEFAULT_LANGUAGE
        await upsert_organization_ai_model_configuration_v2(org_id, existing)

    async def _apply_org_preferences(self, config: AgentWizardConfig, org_id: int) -> None:
        if config.business_hours is None:
            return
        from api.schemas.organization_preferences import OrganizationPreferences

        prefs = OrganizationPreferences(timezone=config.business_hours.timezone)
        await upsert_organization_preferences(org_id, prefs)

    async def _store_vertical_binding(self, config: AgentWizardConfig, org_id: int) -> None:
        if config.industry is None or not config.industry.template_id:
            return
        from api.services.vertical_workflows.registry import get_vertical_workflow_registry

        template = get_vertical_workflow_registry().get(config.industry.template_id)
        template_version = template.version if template else "1.0.0"
        row = await db_client.get_configuration(
            org_id, OrganizationConfigurationKey.VERTICAL_WORKFLOW_CONFIGURATION.value
        )
        value = normalize_org_config(dict(row.value) if row and row.value else {})
        templates = value.get("templates", {})
        templates[config.industry.template_id] = {
            "default_locale": config.locale.primary_locale if config.locale else "mixed",
            "pinned_version": template_version,
            "metadata": {"source": "agent_wizard"},
        }
        await db_client.upsert_configuration(
            org_id,
            OrganizationConfigurationKey.VERTICAL_WORKFLOW_CONFIGURATION.value,
            {"templates": templates},
        )


_engine: AgentWizardEngine | None = None


def get_agent_wizard_engine() -> AgentWizardEngine:
    global _engine
    if _engine is None:
        _engine = AgentWizardEngine()
    return _engine
