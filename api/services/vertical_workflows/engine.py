"""Vertical workflow execution engine."""

from __future__ import annotations

from typing import Any

from api.constants import VERTICAL_WORKFLOWS_ENABLED
from api.services.vertical_workflows.integration import get_vertical_workflow_integration
from api.services.vertical_workflows.loader import get_vertical_template_loader
from api.services.vertical_workflows.rules import get_business_rule_engine
from api.services.vertical_workflows.schema import (
    RuleActionType,
    VerticalWorkflowInstance,
    VerticalWorkflowTemplate,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowExecutionResult,
    WorkflowInstanceStatus,
    WorkflowStep,
)
from api.services.vertical_workflows.store import get_vertical_workflow_store


class VerticalWorkflowEngine:
    """Execute vertical business-agent workflows with rules and integrations."""

    def __init__(self) -> None:
        self._loader = get_vertical_template_loader()
        self._rules = get_business_rule_engine()
        self._store = get_vertical_workflow_store()
        self._integration = get_vertical_workflow_integration()

    @property
    def enabled(self) -> bool:
        return VERTICAL_WORKFLOWS_ENABLED

    async def start(
        self,
        *,
        template_id: str,
        organization_id: int,
        workflow_run_id: int | None = None,
        locale: str | None = None,
        initial_variables: dict[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        template = await self._loader.load(template_id, organization_id=organization_id)
        loc = locale or template.default_locale
        instance = self._store.create(
            template_id=template_id,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            locale=loc,
            variables=initial_variables,
            entry_step_id=template.entry_step_id,
        )
        self._store.append_history(
            instance,
            event_type=WorkflowEventType.START.value,
            payload={"template_id": template_id, "locale": loc},
        )
        await self._store.persist_to_workflow_run(instance)
        return await self.process_event(
            instance.instance_id,
            WorkflowEvent(WorkflowEventType.START, {}),
        )

    async def process_event(
        self,
        instance_id: str,
        event: WorkflowEvent,
    ) -> WorkflowExecutionResult:
        instance = self._store.require(instance_id)
        template = await self._loader.load(
            instance.template_id,
            organization_id=instance.organization_id,
        )

        if event.event_type == WorkflowEventType.MANUAL and event.payload.get("step_id"):
            instance.current_step_id = str(event.payload["step_id"])

        context = self._build_context(instance, event)
        step = template.step(instance.current_step_id) or template.entry_step()
        if step is None:
            instance.status = WorkflowInstanceStatus.FAILED
            self._store.save(instance)
            return self._result(instance, template, step, [])

        rules = template.global_rules + step.rules
        actions = self._rules.evaluate(rules, context)

        actions_taken: list[dict[str, Any]] = []
        for action in actions:
            outcome = await self._integration.dispatch(
                action,
                instance=instance,
                template=template,
                context=context,
            )
            actions_taken.append(outcome)

            if action.action == RuleActionType.ADVANCE_STEP and step.next_step_id:
                if not action.params.get("step_id"):
                    instance.current_step_id = step.next_step_id

        self._store.append_history(
            instance,
            event_type=event.event_type.value,
            payload={"context": context, "actions": actions_taken},
        )
        self._store.save(instance)
        await self._store.persist_to_workflow_run(instance)

        current_step = template.step(instance.current_step_id) or step
        return self._result(instance, template, current_step, actions_taken)

    async def get_instance(self, instance_id: str) -> VerticalWorkflowInstance | None:
        return self._store.get(instance_id)

    async def get_prompt(
        self,
        instance_id: str,
        *,
        locale: str | None = None,
    ) -> str:
        instance = self._store.require(instance_id)
        template = await self._loader.load(
            instance.template_id,
            organization_id=instance.organization_id,
        )
        step = template.step(instance.current_step_id) or template.entry_step()
        if step is None:
            return ""
        loc = locale or instance.locale or template.default_locale
        return step.prompts.resolve(loc, kind="system")

    def _build_context(
        self,
        instance: VerticalWorkflowInstance,
        event: WorkflowEvent,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            **instance.variables,
            "locale": instance.locale,
            "current_step_id": instance.current_step_id,
            "organization_id": instance.organization_id,
            "workflow_run_id": instance.workflow_run_id,
            "event_type": event.event_type.value,
        }
        context.update(event.payload)
        intent = context.get("intent")
        if isinstance(intent, dict):
            context["intent"] = intent.get("name") or intent.get("intent")
            context.setdefault(
                "intent_confidence",
                intent.get("confidence", 1.0),
            )
        return context

    def _result(
        self,
        instance: VerticalWorkflowInstance,
        template: VerticalWorkflowTemplate,
        step: WorkflowStep | None,
        actions_taken: list[dict[str, Any]],
    ) -> WorkflowExecutionResult:
        loc = instance.locale or template.default_locale
        prompt = step.prompts.resolve(loc, kind="system") if step else ""
        return WorkflowExecutionResult(
            instance_id=instance.instance_id,
            status=instance.status,
            current_step_id=instance.current_step_id,
            actions_taken=actions_taken,
            variables=dict(instance.variables),
            prompt=prompt,
            escalated=bool(instance.variables.get("escalated")),
            payment_requested=bool(instance.variables.get("payment_requested")),
        )


_engine: VerticalWorkflowEngine | None = None


def get_vertical_workflow_engine() -> VerticalWorkflowEngine:
    global _engine
    if _engine is None:
        _engine = VerticalWorkflowEngine()
    return _engine
