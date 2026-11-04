"""Tests for self-serve agent wizard."""

from __future__ import annotations

import pytest

from api.services.agent_wizard.schema import (
    AgentWizardConfig,
    BusinessHoursConfig,
    IndustrySelection,
    LocaleConfig,
    PhoneConfig,
    VoiceConfig,
    WorkflowSelection,
)
from api.services.agent_wizard.state_machine import (
    WizardStep,
    can_transition,
    infer_step_from_config,
    next_step,
    progress_percent,
)
from api.services.agent_wizard.validation import validate_for_deploy, validate_step
from api.services.agent_wizard.workflow_builder import build_workflow_definition


def _full_config() -> AgentWizardConfig:
    return AgentWizardConfig(
        industry=IndustrySelection(
            industry_id="fintech_kenya",
            template_id="kenya_fintech_support",
            template_source="vertical",
        ),
        workflow=WorkflowSelection(
            agent_name="Acme Support Bot",
            call_direction="inbound",
            use_case="Customer support",
            activity_description="Answer balance and transaction questions for mobile money users.",
        ),
        locale=LocaleConfig(primary_locale="mixed", kenyan_language_mode="mixed"),
        voice=VoiceConfig(voice_id="default", speed=1.0),
        business_hours=BusinessHoursConfig(timezone="Africa/Nairobi"),
        phone=PhoneConfig(
            telephony_configuration_id=1,
            address="+254712345678",
            country_code="KE",
            skip_assignment=False,
        ),
    )


class TestStateMachine:
    def test_step_order(self):
        assert next_step(WizardStep.INDUSTRY) == WizardStep.WORKFLOW
        assert next_step(WizardStep.REVIEW) == WizardStep.COMPLETED

    def test_can_transition_forward_one(self):
        assert can_transition(WizardStep.INDUSTRY, WizardStep.WORKFLOW)
        assert not can_transition(WizardStep.INDUSTRY, WizardStep.VOICE)

    def test_infer_step_from_partial_config(self):
        cfg = AgentWizardConfig(industry=IndustrySelection(industry_id="retail"))
        assert infer_step_from_config(cfg) == WizardStep.WORKFLOW

    def test_progress_percent(self):
        assert progress_percent(WizardStep.INDUSTRY) == 0
        assert progress_percent(WizardStep.COMPLETED) == 100


class TestValidation:
    def test_industry_requires_known_id(self):
        cfg = AgentWizardConfig(
            industry=IndustrySelection(industry_id="not_real"),
        )
        result = validate_step(WizardStep.INDUSTRY, cfg)
        assert not result.valid

    def test_workflow_requires_description(self):
        cfg = AgentWizardConfig(
            workflow=WorkflowSelection(
                agent_name="Bot",
                use_case="Support",
                activity_description="short",
            )
        )
        result = validate_step(WizardStep.WORKFLOW, cfg)
        assert not result.valid

    def test_inbound_can_skip_phone_for_later(self):
        cfg = _full_config()
        cfg.phone = PhoneConfig(skip_assignment=True)
        result = validate_step(WizardStep.PHONE, cfg)
        assert result.valid

    def test_full_config_passes_review(self):
        result = validate_for_deploy(_full_config())
        assert result.valid


class TestWorkflowBuilder:
    def test_builds_start_agent_end_graph(self):
        definition = build_workflow_definition(_full_config())
        types = {n["type"] for n in definition["nodes"]}
        assert "startCall" in types
        assert "agentNode" in types
        assert "endCall" in types
        assert len(definition["edges"]) >= 2
        names = {n["data"]["name"] for n in definition["nodes"]}
        assert "Greeting" in names


class TestKenyaMarketplace:
    def test_twenty_five_industry_templates(self):
        from api.services.agent_wizard.industries import list_industry_options
        from api.services.vertical_workflows.registry import get_vertical_workflow_registry
        from api.services.vertical_workflows.templates.kenya_marketplace import (
            KENYA_INDUSTRY_SPECS,
            TEMPLATE_VERSION,
        )

        assert len(KENYA_INDUSTRY_SPECS) == 25
        assert len(list_industry_options()) == 25
        registry = get_vertical_workflow_registry()
        required_kinds = {
            "greeting",
            "language_select",
            "identify",
            "faq",
            "collect",
            "escalation",
            "summary",
        }
        for spec in KENYA_INDUSTRY_SPECS:
            template = registry.require(f"kenya_mp_{spec.industry_id}")
            assert template.version == TEMPLATE_VERSION
            kinds = {s.kind.value for s in template.steps}
            assert required_kinds.issubset(kinds)
            assert template.integrations.phone_ke
            assert template.integrations.kes
            meta = template.metadata
            assert "changelog" in meta
            assert "required_env" in meta
            assert meta.get("pin_on_install") is True

    def test_generated_graph_pins_template_version(self):
        from api.services.agent_wizard.workflow_builder import build_workflow_configurations

        meta = build_workflow_configurations(_full_config())
        assert meta["agent_wizard"]["template_id"] == "kenya_fintech_support"
        assert meta["agent_wizard"]["template_version"] == "1.0.0"

    def test_outbound_includes_trigger(self):
        cfg = _full_config()
        cfg.workflow = cfg.workflow.model_copy(update={"call_direction": "outbound"})
        cfg.phone = PhoneConfig(skip_assignment=True)
        definition = build_workflow_definition(cfg)
        types = {n["type"] for n in definition["nodes"]}
        assert "trigger" in types
