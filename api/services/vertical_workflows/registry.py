"""Vertical workflow template registry."""

from __future__ import annotations

from typing import Any

from api.services.vertical_workflows.schema import VerticalIndustry, VerticalWorkflowTemplate
from api.services.vertical_workflows.templates.builtin import BUILTIN_TEMPLATES


class VerticalWorkflowRegistry:
    """In-process registry of vertical workflow templates."""

    def __init__(self) -> None:
        self._templates: dict[str, VerticalWorkflowTemplate] = {}

    def register(self, template: VerticalWorkflowTemplate) -> None:
        self._templates[template.template_id] = template

    def unregister(self, template_id: str) -> None:
        self._templates.pop(template_id, None)

    def get(self, template_id: str) -> VerticalWorkflowTemplate | None:
        return self._templates.get(template_id)

    def require(self, template_id: str) -> VerticalWorkflowTemplate:
        template = self.get(template_id)
        if template is None:
            raise KeyError(f"Vertical workflow template not found: {template_id}")
        return template

    def list_templates(
        self,
        *,
        industry: VerticalIndustry | None = None,
    ) -> list[VerticalWorkflowTemplate]:
        items = list(self._templates.values())
        if industry is not None:
            items = [t for t in items if t.industry == industry]
        return sorted(items, key=lambda t: (t.industry.value, t.name))

    def summary(self) -> list[dict[str, Any]]:
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "industry": t.industry.value,
                "version": t.version,
                "description": t.description,
                "supported_locales": list(t.supported_locales),
                "integrations": t.integrations.to_dict(),
            }
            for t in self.list_templates()
        ]


_registry = VerticalWorkflowRegistry()


def get_vertical_workflow_registry() -> VerticalWorkflowRegistry:
    if not _registry._templates:
        for template in BUILTIN_TEMPLATES:
            _registry.register(template)
    return _registry
