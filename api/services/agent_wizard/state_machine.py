"""Onboarding state machine for agent setup wizard."""

from __future__ import annotations

from enum import Enum

from api.services.agent_wizard.schema import AgentWizardConfig


class WizardStep(str, Enum):
    INDUSTRY = "industry"
    WORKFLOW = "workflow"
    LANGUAGE = "language"
    PAYMENTS = "payments"
    CRM = "crm"
    ESCALATION = "escalation"
    VOICE = "voice"
    BUSINESS_HOURS = "business_hours"
    PHONE = "phone"
    WEBSITE = "website"
    KNOWLEDGE_SOURCES = "knowledge_sources"
    INTEGRATIONS = "integrations"
    REVIEW_DISCOVERED = "review_discovered"
    TEST_AGENT = "test_agent"
    REVIEW = "review"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    FAILED = "failed"


STEP_ORDER: tuple[WizardStep, ...] = (
    WizardStep.INDUSTRY,
    WizardStep.WORKFLOW,
    WizardStep.LANGUAGE,
    WizardStep.PAYMENTS,
    WizardStep.CRM,
    WizardStep.ESCALATION,
    WizardStep.VOICE,
    WizardStep.BUSINESS_HOURS,
    WizardStep.PHONE,
    WizardStep.WEBSITE,
    WizardStep.KNOWLEDGE_SOURCES,
    WizardStep.INTEGRATIONS,
    WizardStep.REVIEW_DISCOVERED,
    WizardStep.TEST_AGENT,
    WizardStep.REVIEW,
    WizardStep.COMPLETED,
)

TERMINAL_STEPS = frozenset({WizardStep.COMPLETED, WizardStep.FAILED, WizardStep.DEPLOYING})


def step_index(step: WizardStep) -> int:
    try:
        return STEP_ORDER.index(step)
    except ValueError:
        return -1


def next_step(step: WizardStep) -> WizardStep | None:
    idx = step_index(step)
    if idx < 0 or idx >= len(STEP_ORDER) - 1:
        return None
    return STEP_ORDER[idx + 1]


def previous_step(step: WizardStep) -> WizardStep | None:
    idx = step_index(step)
    if idx <= 0:
        return None
    return STEP_ORDER[idx - 1]


def can_transition(current: WizardStep, target: WizardStep) -> bool:
    if current in TERMINAL_STEPS and target != WizardStep.FAILED:
        return False
    if target == WizardStep.FAILED:
        return True
    if target == WizardStep.DEPLOYING:
        return current == WizardStep.REVIEW
    if target == WizardStep.COMPLETED:
        return current in {WizardStep.DEPLOYING, WizardStep.REVIEW}
    cur_idx = step_index(current)
    tgt_idx = step_index(target)
    if cur_idx < 0 or tgt_idx < 0:
        return False
    return tgt_idx <= cur_idx + 1


def infer_step_from_config(config: AgentWizardConfig) -> WizardStep:
    """Best-effort step inference when resuming a session."""
    if config.phone is not None:
        if not config.test_completed:
            if not config.discovered_reviewed:
                if not config.integrations_ready:
                    if not config.knowledge_ready:
                        if not config.website_url:
                            return WizardStep.WEBSITE
                        return WizardStep.KNOWLEDGE_SOURCES
                    return WizardStep.INTEGRATIONS
                return WizardStep.REVIEW_DISCOVERED
            return WizardStep.TEST_AGENT
        return WizardStep.REVIEW
    if config.business_hours is not None:
        return WizardStep.PHONE
    if config.voice is not None or config.personality is not None:
        return WizardStep.BUSINESS_HOURS
    if config.escalation is not None:
        return WizardStep.VOICE
    if config.crm is not None:
        return WizardStep.ESCALATION
    if config.payments is not None:
        return WizardStep.CRM
    if config.locale is not None:
        return WizardStep.PAYMENTS
    if config.workflow is not None:
        return WizardStep.LANGUAGE
    if config.industry is not None:
        return WizardStep.WORKFLOW
    return WizardStep.INDUSTRY


def progress_percent(step: WizardStep) -> int:
    if step == WizardStep.COMPLETED:
        return 100
    if step == WizardStep.FAILED:
        return 0
    idx = step_index(step)
    if idx < 0:
        return 0
    total = len(STEP_ORDER) - 1
    return min(100, int(round(idx / total * 100)))
