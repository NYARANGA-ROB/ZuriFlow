"""School fee reminders marketplace template."""

from __future__ import annotations

from api.services.template_marketplace.schema import MarketplaceTemplateListing, TemplateVersionInfo
from api.services.template_marketplace.templates._helpers import (
    base_template,
    closing_step,
    escalate_rule,
    greeting_step,
    payment_rule,
)
from api.services.vertical_workflows.schema import (
    IntegrationBindings,
    MultilingualPrompt,
    VerticalIndustry,
    WorkflowStep,
    WorkflowStepKind,
)

_SCHOOL_TEMPLATE = base_template(
    template_id="school_fee_reminders",
    name="School Fee Reminders",
    industry=VerticalIndustry.EDUCATION,
    description=(
        "Term fee reminders, balance inquiries, M-Pesa school fee collection, "
        "and parent communication in English and Swahili."
    ),
    version="1.0.0",
    integrations=IntegrationBindings(
        mpesa=True, whatsapp=True, call_routing=True, kenyan_intent=True
    ),
    metadata={"region": "KE", "use_cases": ["school_fees", "reminders", "parents"]},
    steps=(
        greeting_step(
            next_step_id="student_lookup",
            prompts={
                "en": "You are calling from {{school_name}} about school fees. Greet the parent politely.",
                "sw": "Unapiga simu kutoka {{school_name}} kuhusu ada ya shule. Salimu mzazi kwa heshima.",
                "mixed": "You represent {{school_name}} regarding school fees. Use the parent's language.",
            },
        ),
        WorkflowStep(
            step_id="student_lookup",
            name="Student Lookup",
            kind=WorkflowStepKind.QUALIFY,
            next_step_id="fee_discussion",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Confirm student name, class, and admission number before discussing balance.",
                },
            ),
        ),
        WorkflowStep(
            step_id="fee_discussion",
            name="Fee Balance Discussion",
            kind=WorkflowStepKind.NEGOTIATION,
            next_step_id="collect_payment",
            rules=(
                payment_rule("school_fee_payment", intent="pay_fees"),
                escalate_rule("fee_dispute", intent="dispute"),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": (
                        "State outstanding term balance and due date. "
                        "Offer M-Pesa payment or a short installment plan if policy allows."
                    ),
                },
            ),
        ),
        WorkflowStep(
            step_id="collect_payment",
            name="Collect School Fees",
            kind=WorkflowStepKind.COLLECT_PAYMENT,
            next_step_id="closing",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={"mixed": "Send M-Pesa STK push for the agreed amount and confirm receipt."},
            ),
        ),
        closing_step(
            prompts={
                "mixed": "Confirm payment and remind parent of next term dates or remaining balance.",
            }
        ),
    ),
)

SCHOOL_FEE_REMINDERS_LISTING = MarketplaceTemplateListing(
    template_id="school_fee_reminders",
    template=_SCHOOL_TEMPLATE,
    tags=("education", "school", "fees", "mpesa", "parents"),
    search_keywords=(
        "school",
        "fees",
        "tuition",
        "parent",
        "shule",
        "ada",
        "mzazi",
        "term",
    ),
    category="education",
    featured=True,
    icon="graduation-cap",
    version_history=(
        TemplateVersionInfo(
            version="1.0.0",
            released_at="2026-06-01",
            changelog="School fee reminders with M-Pesa collection for Kenyan schools.",
        ),
    ),
)
