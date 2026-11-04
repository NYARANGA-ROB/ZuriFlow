"""Step validation for the agent setup wizard."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.services.agent_wizard.industries import get_industry_option
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
from api.services.agent_wizard.state_machine import WizardStep
from api.services.vertical_workflows.registry import get_vertical_workflow_registry


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def fail(cls, *errors: str) -> "ValidationResult":
        return cls(valid=False, errors=list(errors))


def validate_industry(selection: IndustrySelection) -> ValidationResult:
    opt = get_industry_option(selection.industry_id)
    if opt is None:
        return ValidationResult.fail(f"Unknown industry: {selection.industry_id}")
    if selection.template_id:
        registry = get_vertical_workflow_registry()
        if registry.get(selection.template_id) is None:
            return ValidationResult.fail(f"Unknown template: {selection.template_id}")
    return ValidationResult.ok()


def validate_workflow(selection: WorkflowSelection) -> ValidationResult:
    errors: list[str] = []
    if len(selection.agent_name.strip()) < 2:
        errors.append("Agent name must be at least 2 characters")
    if not selection.use_case.strip():
        errors.append("Use case is required")
    if len(selection.activity_description.strip()) < 10:
        errors.append("Describe what the agent should do (at least 10 characters)")
    if errors:
        return ValidationResult.fail(*errors)
    return ValidationResult.ok()


def validate_locale(selection: LocaleConfig) -> ValidationResult:
    if selection.primary_locale not in {"en", "sw", "mixed", "fr", "sheng"}:
        return ValidationResult.fail("Invalid primary locale")
    return ValidationResult.ok()


def validate_payments(_selection: PaymentsConfig) -> ValidationResult:
    return ValidationResult.ok()


def validate_crm(_selection: CrmConfig) -> ValidationResult:
    return ValidationResult.ok()


def validate_escalation(_selection: EscalationConfig) -> ValidationResult:
    return ValidationResult.ok()


def validate_personality(_selection: PersonalityConfig) -> ValidationResult:
    return ValidationResult.ok()


def validate_voice(selection: VoiceConfig) -> ValidationResult:
    if not selection.voice_id.strip():
        return ValidationResult.fail("Voice selection is required")
    return ValidationResult.ok()


def validate_business_hours(selection: BusinessHoursConfig) -> ValidationResult:
    if not selection.timezone.strip():
        return ValidationResult.fail("Timezone is required")
    for day, sched in selection.schedule.items():
        if not sched.enabled:
            continue
        if sched.open_time >= sched.close_time:
            return ValidationResult.fail(
                f"{day.title()}: open time must be before close time"
            )
    return ValidationResult.ok()


def validate_phone(selection: PhoneConfig, *, call_direction: str) -> ValidationResult:
    if selection.skip_assignment:
        return ValidationResult.ok()
    if not selection.address or not selection.address.strip():
        return ValidationResult.fail("Phone number address is required")
    if selection.telephony_configuration_id is None:
        return ValidationResult.fail("Select a telephony configuration")
    return ValidationResult.ok()


def validate_step(step: WizardStep, config: AgentWizardConfig) -> ValidationResult:
    if step == WizardStep.INDUSTRY:
        if config.industry is None:
            return ValidationResult.fail("Select an industry")
        return validate_industry(config.industry)
    if step == WizardStep.WORKFLOW:
        if config.workflow is None:
            return ValidationResult.fail("Configure your agent")
        return validate_workflow(config.workflow)
    if step == WizardStep.LANGUAGE:
        if config.locale is None:
            return ValidationResult.fail("Select languages")
        return validate_locale(config.locale)
    if step == WizardStep.PAYMENTS:
        return validate_payments(config.payments or PaymentsConfig())
    if step == WizardStep.CRM:
        return validate_crm(config.crm or CrmConfig())
    if step == WizardStep.ESCALATION:
        return validate_escalation(config.escalation or EscalationConfig())
    if step == WizardStep.VOICE:
        if config.voice is None:
            return ValidationResult.fail("Select a voice")
        return validate_voice(config.voice)
    if step == WizardStep.BUSINESS_HOURS:
        if config.business_hours is None:
            return ValidationResult.fail("Configure business hours")
        return validate_business_hours(config.business_hours)
    if step == WizardStep.PHONE:
        if config.phone is None:
            return ValidationResult.fail("Configure phone assignment")
        direction = config.workflow.call_direction if config.workflow else "inbound"
        return validate_phone(config.phone, call_direction=direction)
    if step == WizardStep.REVIEW:
        for prior in (
            WizardStep.INDUSTRY,
            WizardStep.WORKFLOW,
            WizardStep.LANGUAGE,
            WizardStep.VOICE,
            WizardStep.BUSINESS_HOURS,
            WizardStep.PHONE,
        ):
            result = validate_step(prior, config)
            if not result.valid:
                return result
        return ValidationResult.ok()
    return ValidationResult.ok()


def validate_for_deploy(config: AgentWizardConfig) -> ValidationResult:
    return validate_step(WizardStep.REVIEW, config)
