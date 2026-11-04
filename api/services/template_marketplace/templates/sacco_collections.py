"""SACCO collections marketplace template — extends debt collection."""

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

_SACCO_TEMPLATE = base_template(
    template_id="sacco_collections",
    name="SACCO Loan Collections",
    industry=VerticalIndustry.SACCO,
    description=(
        "Member loan reminders, share contribution follow-ups, and M-Pesa "
        "repayment collection for Kenyan SACCOs."
    ),
    version="1.0.0",
    extends_template_id="debt_collection",
    extends_version="1.0.0",
    integrations=IntegrationBindings(
        mpesa=True, whatsapp=True, call_routing=True, kenyan_intent=True
    ),
    metadata={"region": "KE", "use_cases": ["sacco", "loan", "shares", "dividend"]},
    steps=(
        greeting_step(
            next_step_id="member_verify",
            prompts={
                "mixed": (
                    "You are a collections agent for {{sacco_name}} SACCO. "
                    "Greet the member warmly and confirm their membership number."
                ),
            },
        ),
        WorkflowStep(
            step_id="member_verify",
            name="Member Verification",
            kind=WorkflowStepKind.QUALIFY,
            next_step_id="collections",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Verify member ID and outstanding loan or share balance before discussing payment.",
                },
            ),
        ),
        WorkflowStep(
            step_id="collections",
            name="Loan & Share Collections",
            kind=WorkflowStepKind.NEGOTIATION,
            next_step_id="collect_payment",
            rules=(
                payment_rule("sacco_payment"),
                escalate_rule("sacco_escalation", intent="dispute"),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": (
                        "Discuss outstanding loan balance or share arrears. "
                        "Offer M-Pesa STK push or installment plan."
                    ),
                },
            ),
        ),
        WorkflowStep(
            step_id="collect_payment",
            name="M-Pesa Collection",
            kind=WorkflowStepKind.COLLECT_PAYMENT,
            next_step_id="closing",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={"mixed": "Initiate M-Pesa payment and confirm receipt number."},
            ),
        ),
        closing_step(
            prompts={
                "mixed": "Thank the member and confirm updated balance or next payment date.",
            }
        ),
    ),
)

SACCO_COLLECTIONS_LISTING = MarketplaceTemplateListing(
    template_id="sacco_collections",
    template=_SACCO_TEMPLATE,
    tags=("sacco", "collections", "mpesa", "loan", "cooperative"),
    search_keywords=(
        "sacco",
        "chama",
        "cooperative",
        "member",
        "shares",
        "loan",
        "mkopo",
        "dividend",
    ),
    category="finance",
    featured=True,
    icon="users",
    version_history=(
        TemplateVersionInfo(
            version="1.0.0",
            released_at="2026-06-01",
            changelog="SACCO-specific collections inheriting debt collection compliance patterns.",
        ),
    ),
)
