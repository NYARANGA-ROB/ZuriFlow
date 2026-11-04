"""Install marketplace templates as org-scoped voice agents."""

from __future__ import annotations

from api.db import db_client
from api.services.agent_wizard.schema import AgentWizardConfig, IndustrySelection, WorkflowSelection
from api.services.agent_wizard.workflow_builder import (
    build_workflow_configurations,
    build_workflow_definition,
)
from api.services.template_marketplace.customization import get_template_customization_engine
from api.services.workflow.trigger_paths import extract_trigger_paths, regenerate_trigger_uuids


class TemplateInstallService:
    async def install(
        self,
        *,
        template_id: str,
        workflow_name: str,
        user_id: int,
        organization_id: int,
        version: str | None = None,
        call_direction: str = "inbound",
    ) -> dict:
        engine = get_template_customization_engine()
        resolved = await engine.resolve(
            template_id,
            organization_id=organization_id,
            version=version,
        )

        config = AgentWizardConfig(
            industry=IndustrySelection(
                industry_id=resolved.industry.value,
                template_id=template_id,
                template_source="vertical",
            ),
            workflow=WorkflowSelection(
                agent_name=workflow_name,
                call_direction=call_direction,  # type: ignore[arg-type]
                use_case=resolved.metadata.get("use_cases", ["voice agent"])[0]
                if isinstance(resolved.metadata.get("use_cases"), list)
                else resolved.name,
                activity_description=resolved.description,
            ),
        )

        workflow_def = build_workflow_definition(config)
        wf_configs = build_workflow_configurations(config)
        wf_configs["marketplace"] = {
            "template_id": template_id,
            "version": resolved.version,
            "resolved_template_id": resolved.template_id,
        }

        trigger_paths = extract_trigger_paths(workflow_def) if workflow_def else []
        if trigger_paths:
            await db_client.assert_trigger_paths_available(trigger_paths=trigger_paths)

        workflow = await db_client.create_workflow(
            name=workflow_name,
            workflow_definition=workflow_def,
            user_id=user_id,
            organization_id=organization_id,
        )

        await db_client.update_workflow(
            workflow.id,
            name=None,
            workflow_definition=None,
            template_context_variables=None,
            workflow_configurations=wf_configs,
            organization_id=organization_id,
        )

        if trigger_paths:
            await db_client.sync_triggers_for_workflow(
                workflow_id=workflow.id,
                organization_id=organization_id,
                trigger_paths=trigger_paths,
            )

        return {
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "template_id": template_id,
            "template_version": resolved.version,
        }


_installer: TemplateInstallService | None = None


def get_template_install_service() -> TemplateInstallService:
    global _installer
    if _installer is None:
        _installer = TemplateInstallService()
    return _installer
