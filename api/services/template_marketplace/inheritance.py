"""Template inheritance — resolve parent chains and merge payloads."""

from __future__ import annotations

from dataclasses import replace

from api.services.vertical_workflows.schema import (
    IntegrationBindings,
    MultilingualPrompt,
    VerticalWorkflowTemplate,
    WorkflowStep,
)


class TemplateInheritanceResolver:
    """Resolve extends_template_id chains and merge parent into child."""

    def __init__(self) -> None:
        self._resolving: set[str] = set()

    def resolve(
        self,
        template: VerticalWorkflowTemplate,
        *,
        version: str | None = None,
    ) -> VerticalWorkflowTemplate:
        if not template.extends_template_id:
            return template

        chain_key = f"{template.template_id}@{template.version}"
        if chain_key in self._resolving:
            return template
        self._resolving.add(chain_key)
        try:
            from api.services.template_marketplace.registry import (
                get_template_marketplace_registry,
            )

            registry = get_template_marketplace_registry()
            parent_ver = template.extends_version
            parent = registry.require_version(
                template.extends_template_id,
                parent_ver,
            )
            parent_resolved = self.resolve(parent, version=parent_ver)
            return self._merge_parent_child(parent_resolved, template)
        finally:
            self._resolving.discard(chain_key)

    def _merge_parent_child(
        self,
        parent: VerticalWorkflowTemplate,
        child: VerticalWorkflowTemplate,
    ) -> VerticalWorkflowTemplate:
        child_steps = {s.step_id: s for s in child.steps}
        merged_steps: list[WorkflowStep] = []

        for pstep in parent.steps:
            cstep = child_steps.get(pstep.step_id)
            if cstep is None:
                merged_steps.append(pstep)
                continue
            merged_steps.append(self._merge_step(pstep, cstep))

        for cstep in child.steps:
            if cstep.step_id not in {s.step_id for s in parent.steps}:
                merged_steps.append(cstep)

        return replace(
            child,
            steps=tuple(merged_steps),
            global_rules=parent.global_rules + child.global_rules,
            integrations=self._merge_integrations(parent.integrations, child.integrations),
            metadata={**parent.metadata, **child.metadata},
            supported_locales=child.supported_locales or parent.supported_locales,
            default_locale=child.default_locale or parent.default_locale,
        )

    @staticmethod
    def _merge_step(parent: WorkflowStep, child: WorkflowStep) -> WorkflowStep:
        return replace(
            child,
            prompts=TemplateInheritanceResolver._merge_prompts(parent.prompts, child.prompts),
            rules=parent.rules + child.rules,
            next_step_id=child.next_step_id or parent.next_step_id,
            timeout_s=child.timeout_s or parent.timeout_s,
        )

    @staticmethod
    def _merge_prompts(parent: MultilingualPrompt, child: MultilingualPrompt) -> MultilingualPrompt:
        return MultilingualPrompt(
            default_locale=child.default_locale or parent.default_locale,
            system={**parent.system, **child.system},
            user_hint={**parent.user_hint, **child.user_hint},
        )

    @staticmethod
    def _merge_integrations(
        parent: IntegrationBindings,
        child: IntegrationBindings,
    ) -> IntegrationBindings:
        return IntegrationBindings(
            mpesa=child.mpesa or parent.mpesa,
            whatsapp=child.whatsapp or parent.whatsapp,
            call_routing=child.call_routing or parent.call_routing,
            kenyan_intent=child.kenyan_intent or parent.kenyan_intent,
        )


_resolver: TemplateInheritanceResolver | None = None


def get_template_inheritance_resolver() -> TemplateInheritanceResolver:
    global _resolver
    if _resolver is None:
        _resolver = TemplateInheritanceResolver()
    return _resolver
