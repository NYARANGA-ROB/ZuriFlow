"""Tenant customization engine for marketplace templates."""

from __future__ import annotations

from dataclasses import replace

from api.enums import OrganizationConfigurationKey
from api.services.template_marketplace.inheritance import get_template_inheritance_resolver
from api.services.template_marketplace.org_config import normalize_org_config
from api.services.template_marketplace.schema import TenantTemplateCustomization
from api.services.vertical_workflows.schema import (
    BusinessRule,
    MultilingualPrompt,
    VerticalWorkflowTemplate,
    WorkflowStep,
)

ORG_CONFIG_KEY = OrganizationConfigurationKey.VERTICAL_WORKFLOW_CONFIGURATION.value


class TemplateCustomizationEngine:
    """Apply tenant overrides on top of inherited marketplace templates."""

    def __init__(self) -> None:
        self._inheritance = get_template_inheritance_resolver()

    def _registry(self):
        from api.services.template_marketplace.registry import get_template_marketplace_registry

        return get_template_marketplace_registry()

    async def load_org_config(self, organization_id: int) -> dict:
        try:
            from api.db import db_client

            row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
            return normalize_org_config(dict(row.value) if row and row.value else {})
        except Exception:
            return {"templates": {}}

    async def get_customization(
        self,
        organization_id: int,
        template_id: str,
    ) -> TenantTemplateCustomization:
        cfg = await self.load_org_config(organization_id)
        raw = cfg.get("templates", {}).get(template_id)
        return TenantTemplateCustomization.from_dict(template_id, raw)

    async def save_customization(
        self,
        organization_id: int,
        customization: TenantTemplateCustomization,
    ) -> TenantTemplateCustomization:
        from api.db import db_client

        cfg = await self.load_org_config(organization_id)
        templates = dict(cfg.get("templates") or {})
        templates[customization.template_id] = customization.to_dict()
        await db_client.upsert_configuration(
            organization_id,
            ORG_CONFIG_KEY,
            {"templates": templates},
        )
        return customization

    def apply_customization(
        self,
        template: VerticalWorkflowTemplate,
        customization: TenantTemplateCustomization | None,
    ) -> VerticalWorkflowTemplate:
        if customization is None:
            return template

        extra_rules = tuple(
            BusinessRule.from_dict(r) for r in customization.global_rules
        )
        step_overrides = customization.steps
        prompt_overrides = customization.prompt_overrides

        merged_steps: list[WorkflowStep] = []
        for step in template.steps:
            raw = step_overrides.get(step.step_id)
            extra_step_rules = tuple(
                BusinessRule.from_dict(r) for r in (raw or {}).get("rules") or []
            )
            prompts = step.prompts
            if step.step_id in prompt_overrides:
                prompts = MultilingualPrompt(
                    default_locale=prompts.default_locale,
                    system={**prompts.system, **prompt_overrides[step.step_id]},
                    user_hint=dict(prompts.user_hint),
                )
            merged_steps.append(
                replace(step, rules=step.rules + extra_step_rules, prompts=prompts)
            )

        return replace(
            template,
            global_rules=template.global_rules + extra_rules,
            steps=tuple(merged_steps),
            default_locale=customization.default_locale or template.default_locale,
            metadata={**template.metadata, **customization.metadata},
        )

    async def resolve(
        self,
        template_id: str,
        *,
        organization_id: int | None = None,
        version: str | None = None,
    ) -> VerticalWorkflowTemplate:
        customization: TenantTemplateCustomization | None = None
        pinned: str | None = version

        if organization_id is not None:
            customization = await self.get_customization(organization_id, template_id)
            if customization.pinned_version and pinned is None:
                pinned = customization.pinned_version

        try:
            base = self._registry().require_version(template_id, pinned)
        except KeyError:
            from api.services.vertical_workflows.registry import (
                get_vertical_workflow_registry,
            )

            base = get_vertical_workflow_registry().require(template_id)
        inherited = self._inheritance.resolve(base, version=pinned)
        return self.apply_customization(inherited, customization)


_engine: TemplateCustomizationEngine | None = None


def get_template_customization_engine() -> TemplateCustomizationEngine:
    global _engine
    if _engine is None:
        _engine = TemplateCustomizationEngine()
    return _engine
