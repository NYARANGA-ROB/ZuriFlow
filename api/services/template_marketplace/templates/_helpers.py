"""Shared builders for marketplace vertical templates."""

from __future__ import annotations

from api.services.vertical_workflows.schema import (
    BusinessRule,
    IntegrationBindings,
    MultilingualPrompt,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleOperator,
    VerticalIndustry,
    VerticalWorkflowTemplate,
    WorkflowStep,
    WorkflowStepKind,
)


def escalate_rule(rule_id: str, *, intent: str, priority: int = 10) -> BusinessRule:
    return BusinessRule(
        rule_id=rule_id,
        name=f"Escalate on {intent}",
        when=RuleCondition("intent", RuleOperator.INTENT_IS, intent),
        then=(
            RuleAction(RuleActionType.ESCALATE, {"reason": intent}),
            RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "escalation"}),
        ),
        priority=priority,
    )


def payment_rule(rule_id: str, *, intent: str = "payment") -> BusinessRule:
    return BusinessRule(
        rule_id=rule_id,
        name="Collect M-Pesa payment",
        when=RuleCondition("intent", RuleOperator.INTENT_IS, intent),
        then=(
            RuleAction(RuleActionType.REQUEST_PAYMENT, {}),
            RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "collect_payment"}),
        ),
        priority=20,
    )


def greeting_step(
    *,
    next_step_id: str,
    prompts: dict[str, str],
    default_locale: str = "mixed",
) -> WorkflowStep:
    return WorkflowStep(
        step_id="greeting",
        name="Greeting",
        kind=WorkflowStepKind.GREETING,
        next_step_id=next_step_id,
        prompts=MultilingualPrompt(default_locale=default_locale, system=prompts),
    )


def closing_step(*, prompts: dict[str, str], default_locale: str = "mixed") -> WorkflowStep:
    return WorkflowStep(
        step_id="closing",
        name="Closing",
        kind=WorkflowStepKind.CLOSING,
        prompts=MultilingualPrompt(default_locale=default_locale, system=prompts),
    )


def escalation_step(*, prompts: dict[str, str] | None = None) -> WorkflowStep:
    return WorkflowStep(
        step_id="escalation",
        name="Human Escalation",
        kind=WorkflowStepKind.ESCALATION,
        next_step_id="closing",
        prompts=MultilingualPrompt(
            default_locale="mixed",
            system=prompts
            or {
                "mixed": "Apologize for the difficulty and transfer to a human agent.",
            },
        ),
    )


def base_template(
    *,
    template_id: str,
    name: str,
    industry: VerticalIndustry,
    description: str,
    version: str,
    steps: tuple[WorkflowStep, ...],
    integrations: IntegrationBindings | None = None,
    metadata: dict | None = None,
    default_locale: str = "mixed",
    supported_locales: tuple[str, ...] = ("en", "sw", "mixed"),
    global_rules: tuple[BusinessRule, ...] = (),
    extends_template_id: str | None = None,
    extends_version: str | None = None,
) -> VerticalWorkflowTemplate:
    return VerticalWorkflowTemplate(
        template_id=template_id,
        name=name,
        industry=industry,
        version=version,
        description=description,
        default_locale=default_locale,
        supported_locales=supported_locales,
        entry_step_id="greeting",
        steps=steps,
        global_rules=global_rules,
        integrations=integrations or IntegrationBindings(),
        metadata=metadata or {},
        extends_template_id=extends_template_id,
        extends_version=extends_version,
    )
