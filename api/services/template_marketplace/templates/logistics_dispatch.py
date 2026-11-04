"""Logistics dispatch marketplace template."""

from __future__ import annotations

from api.services.template_marketplace.schema import MarketplaceTemplateListing, TemplateVersionInfo
from api.services.template_marketplace.templates._helpers import (
    base_template,
    closing_step,
    escalate_rule,
    greeting_step,
)
from api.services.vertical_workflows.schema import (
    BusinessRule,
    IntegrationBindings,
    MultilingualPrompt,
    VerticalIndustry,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleOperator,
    WorkflowStep,
    WorkflowStepKind,
)

_LOGISTICS_TEMPLATE = base_template(
    template_id="logistics_dispatch",
    name="Logistics Dispatch Agent",
    industry=VerticalIndustry.LOGISTICS,
    description=(
        "Driver dispatch, delivery status updates, route changes, "
        "and customer ETA notifications in English and Swahili."
    ),
    version="1.0.0",
    integrations=IntegrationBindings(
        mpesa=False, whatsapp=True, call_routing=True, kenyan_intent=True
    ),
    metadata={"region": "KE", "use_cases": ["dispatch", "tracking", "delivery"]},
    steps=(
        greeting_step(
            next_step_id="dispatch",
            prompts={
                "en": "You are a dispatch coordinator for {{company_name}}. Confirm caller identity and order reference.",
                "sw": "Wewe ni msimamizi wa usafirishaji wa {{company_name}}. Thibitisha utambulisho na nambari ya oda.",
                "mixed": "You are a logistics dispatch agent for {{company_name}}. Respond in the caller's language.",
            },
        ),
        WorkflowStep(
            step_id="dispatch",
            name="Dispatch & Routing",
            kind=WorkflowStepKind.SUPPORT,
            next_step_id="tracking",
            rules=(
                BusinessRule(
                    rule_id="assign_driver",
                    name="Assign driver",
                    when=RuleCondition("intent", RuleOperator.INTENT_IS, "dispatch"),
                    then=(
                        RuleAction(RuleActionType.SET_VARIABLE, {"driver_assigned": True}),
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "tracking"}),
                    ),
                    priority=15,
                ),
                escalate_rule("dispatch_escalation", intent="urgent_delivery"),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Collect pickup/delivery addresses, package details, and urgency. Assign nearest available driver.",
                },
            ),
        ),
        WorkflowStep(
            step_id="tracking",
            name="Delivery Tracking",
            kind=WorkflowStepKind.SUPPORT,
            next_step_id="closing",
            rules=(
                BusinessRule(
                    rule_id="send_eta_whatsapp",
                    name="Send ETA via WhatsApp",
                    when=RuleCondition("eta_confirmed", RuleOperator.EQ, True),
                    then=(
                        RuleAction(
                            RuleActionType.SEND_WHATSAPP,
                            {"template": "delivery_eta"},
                        ),
                    ),
                    priority=10,
                ),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Provide delivery status and ETA. Offer to send tracking link via WhatsApp.",
                },
            ),
        ),
        closing_step(
            prompts={
                "mixed": "Confirm delivery window and thank the customer or driver.",
            }
        ),
    ),
)

LOGISTICS_DISPATCH_LISTING = MarketplaceTemplateListing(
    template_id="logistics_dispatch",
    template=_LOGISTICS_TEMPLATE,
    tags=("logistics", "dispatch", "delivery", "tracking"),
    search_keywords=("delivery", "driver", "courier", "usafirishaji", "parcel", "route"),
    category="operations",
    featured=False,
    icon="truck",
    version_history=(
        TemplateVersionInfo(
            version="1.0.0",
            released_at="2026-06-01",
            changelog="Dispatch and tracking workflow with WhatsApp ETA notifications.",
        ),
    ),
)
