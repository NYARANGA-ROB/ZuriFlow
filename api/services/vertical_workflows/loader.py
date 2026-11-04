"""Load and merge vertical workflow templates with org overrides."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from api.enums import OrganizationConfigurationKey
from api.services.template_marketplace.org_config import normalize_org_config
from api.services.vertical_workflows.registry import get_vertical_workflow_registry
from api.services.vertical_workflows.schema import (
    BusinessRule,
    VerticalIndustry,
    VerticalWorkflowTemplate,
    WorkflowStep,
)

ORG_CONFIG_KEY = OrganizationConfigurationKey.VERTICAL_WORKFLOW_CONFIGURATION.value


class VerticalTemplateLoader:
    """Resolve templates from registry + optional org configuration."""

    def __init__(self) -> None:
        self._registry = get_vertical_workflow_registry()

    async def load_org_overrides(self, organization_id: int) -> dict[str, Any]:
        try:
            from api.db import db_client

            row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
            return normalize_org_config(dict(row.value) if row and row.value else {})
        except Exception:
            return {"templates": {}}

    def merge_template(
        self,
        base: VerticalWorkflowTemplate,
        overrides: dict[str, Any] | None,
    ) -> VerticalWorkflowTemplate:
        if not overrides:
            return base

        template_overrides = overrides.get("templates", {}).get(base.template_id, {})
        if not template_overrides:
            return base

        extra_rules = tuple(
            BusinessRule.from_dict(r)
            for r in template_overrides.get("global_rules") or []
        )
        merged_rules = base.global_rules + extra_rules

        step_overrides: dict[str, dict[str, Any]] = template_overrides.get("steps") or {}
        merged_steps: list[WorkflowStep] = []
        for step in base.steps:
            raw = step_overrides.get(step.step_id)
            if not raw:
                merged_steps.append(step)
                continue
            extra_step_rules = tuple(
                BusinessRule.from_dict(r) for r in raw.get("rules") or []
            )
            merged_steps.append(
                replace(step, rules=step.rules + extra_step_rules)
            )

        return replace(
            base,
            global_rules=merged_rules,
            steps=tuple(merged_steps),
            default_locale=template_overrides.get("default_locale", base.default_locale),
            metadata={**base.metadata, **dict(template_overrides.get("metadata") or {})},
        )

    async def load(
        self,
        template_id: str,
        *,
        organization_id: int | None = None,
    ) -> VerticalWorkflowTemplate:
        from api.services.template_marketplace.customization import (
            get_template_customization_engine,
        )

        if organization_id is not None:
            return await get_template_customization_engine().resolve(
                template_id,
                organization_id=organization_id,
            )
        base = self._registry.require(template_id)
        from api.services.template_marketplace.inheritance import (
            get_template_inheritance_resolver,
        )

        return get_template_inheritance_resolver().resolve(base)

    def list_available(
        self,
        *,
        industry: VerticalIndustry | None = None,
    ) -> list[VerticalWorkflowTemplate]:
        return self._registry.list_templates(industry=industry)


_loader: VerticalTemplateLoader | None = None


def get_vertical_template_loader() -> VerticalTemplateLoader:
    global _loader
    if _loader is None:
        _loader = VerticalTemplateLoader()
    return _loader
