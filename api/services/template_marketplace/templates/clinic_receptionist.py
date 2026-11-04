"""Clinic receptionist marketplace template."""

from __future__ import annotations

from api.services.template_marketplace.schema import MarketplaceTemplateListing, TemplateVersionInfo
from api.services.template_marketplace.templates._helpers import (
    base_template,
    closing_step,
    escalate_rule,
    greeting_step,
)
from api.services.vertical_workflows.schema import (
    IntegrationBindings,
    MultilingualPrompt,
    VerticalIndustry,
    WorkflowStep,
    WorkflowStepKind,
)

_CLINIC_TEMPLATE = base_template(
    template_id="clinic_receptionist",
    name="Clinic Receptionist",
    industry=VerticalIndustry.HEALTHCARE,
    description=(
        "Appointment scheduling, clinic directions, insurance questions, "
        "and patient intake in English and Swahili."
    ),
    version="1.0.0",
    integrations=IntegrationBindings(
        mpesa=False, whatsapp=True, call_routing=True, kenyan_intent=True
    ),
    metadata={"region": "KE", "use_cases": ["appointments", "intake", "triage"]},
    steps=(
        greeting_step(
            next_step_id="intake",
            prompts={
                "en": "You are a friendly clinic receptionist for {{clinic_name}}. Greet the caller and ask how you can help.",
                "sw": "Wewe ni mpokeaji wa kliniki ya {{clinic_name}}. Salimu mteja na uliza jinsi ya kusaidia.",
                "mixed": "You are a clinic receptionist for {{clinic_name}}. Respond in the caller's language.",
            },
        ),
        WorkflowStep(
            step_id="intake",
            name="Patient Intake",
            kind=WorkflowStepKind.QUALIFY,
            next_step_id="scheduling",
            rules=(escalate_rule("intake_emergency", intent="emergency", priority=5),),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Collect patient name, reason for visit, and whether it is an emergency.",
                },
            ),
        ),
        WorkflowStep(
            step_id="scheduling",
            name="Appointment Scheduling",
            kind=WorkflowStepKind.BOOKING,
            next_step_id="closing",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Offer available appointment slots. Confirm date, time, and doctor preference.",
                },
            ),
        ),
        closing_step(
            prompts={
                "mixed": "Confirm appointment details and remind the patient what to bring.",
            }
        ),
    ),
)

CLINIC_RECEPTIONIST_LISTING = MarketplaceTemplateListing(
    template_id="clinic_receptionist",
    template=_CLINIC_TEMPLATE,
    tags=("healthcare", "clinic", "appointments", "reception"),
    search_keywords=(
        "clinic",
        "hospital",
        "doctor",
        "appointment",
        "kliniki",
        "daktari",
        "patient",
    ),
    category="healthcare",
    featured=True,
    icon="heart-pulse",
    version_history=(
        TemplateVersionInfo(
            version="1.0.0",
            released_at="2026-06-01",
            changelog="Appointment scheduling and patient intake for Kenyan clinics.",
        ),
    ),
)
