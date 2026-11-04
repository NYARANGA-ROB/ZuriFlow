"""Built-in vertical workflow templates."""

from __future__ import annotations

from api.services.vertical_workflows.templates.kenya_marketplace import (
    KENYA_MARKETPLACE_TEMPLATES,
)
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


def _escalate_rule(rule_id: str, *, intent: str, priority: int = 10) -> BusinessRule:
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


def _payment_rule(rule_id: str, *, intent: str = "payment") -> BusinessRule:
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


KENYA_FINTECH_SUPPORT = VerticalWorkflowTemplate(
    template_id="kenya_fintech_support",
    name="Kenya Fintech Customer Support",
    industry=VerticalIndustry.FINTECH_KENYA,
    description="Voice support with M-Pesa payments, Swahili/English, and human escalation.",
    default_locale="mixed",
    supported_locales=("en", "sw", "mixed"),
    entry_step_id="greeting",
    integrations=IntegrationBindings(
        mpesa=True,
        whatsapp=True,
        call_routing=True,
        kenyan_intent=True,
    ),
    global_rules=(
        BusinessRule(
            rule_id="low_confidence_escalate",
            name="Escalate on low confidence",
            when=RuleCondition("intent_confidence", RuleOperator.LT, 0.45),
            then=(RuleAction(RuleActionType.ESCALATE, {"reason": "low_confidence"}),),
            priority=5,
        ),
    ),
    steps=(
        WorkflowStep(
            step_id="greeting",
            name="Greeting",
            kind=WorkflowStepKind.GREETING,
            next_step_id="support",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "en": "You are a helpful fintech support agent for Kenyan customers. Be concise and professional.",
                    "sw": "Wewe ni wakala wa msaada wa fedha za kidijitali kwa wateja wa Kenya. Kuwa mfupi na wa kitaalamu.",
                    "mixed": "You are a helpful fintech support agent. Respond in the customer's language (English or Swahili).",
                },
            ),
        ),
        WorkflowStep(
            step_id="support",
            name="Support",
            kind=WorkflowStepKind.SUPPORT,
            next_step_id="closing",
            rules=(
                _payment_rule("support_payment"),
                _escalate_rule("support_escalation", intent="escalation"),
                _escalate_rule("support_human", intent="human_agent"),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Resolve account and transaction questions. Offer M-Pesa payment when the customer wants to pay.",
                },
            ),
        ),
        WorkflowStep(
            step_id="collect_payment",
            name="Collect Payment",
            kind=WorkflowStepKind.COLLECT_PAYMENT,
            next_step_id="closing",
            rules=(
                BusinessRule(
                    rule_id="payment_success",
                    name="Payment succeeded",
                    when=RuleCondition("payment_status", RuleOperator.EQ, "success"),
                    then=(
                        RuleAction(
                            RuleActionType.SEND_WHATSAPP,
                            {"template": "payment_receipt"},
                        ),
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "closing"}),
                    ),
                    priority=10,
                ),
                BusinessRule(
                    rule_id="payment_failed",
                    name="Payment failed",
                    when=RuleCondition("payment_status", RuleOperator.EQ, "failed"),
                    then=(RuleAction(RuleActionType.ESCALATE, {"reason": "payment_failed"}),),
                    priority=15,
                ),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Guide the customer through M-Pesa STK push. Confirm amount and phone number.",
                },
            ),
        ),
        WorkflowStep(
            step_id="escalation",
            name="Escalation",
            kind=WorkflowStepKind.ESCALATION,
            next_step_id="closing",
            rules=(
                BusinessRule(
                    rule_id="route_human",
                    name="Route to human queue",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(
                        RuleAction(RuleActionType.ROUTE_QUEUE, {"queue": "human_support"}),
                    ),
                    priority=1,
                ),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Apologize and inform the customer they are being transferred to a human agent.",
                },
            ),
        ),
        WorkflowStep(
            step_id="closing",
            name="Closing",
            kind=WorkflowStepKind.CLOSING,
            rules=(
                BusinessRule(
                    rule_id="end_call",
                    name="End workflow",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(RuleAction(RuleActionType.END_WORKFLOW, {}),),
                    priority=1,
                ),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Thank the customer and confirm next steps before ending the call.",
                },
            ),
        ),
    ),
    metadata={"compliance": ["cbk_voice_disclosure"], "region": "KE"},
)


KENYA_RETAIL_BOOKING = VerticalWorkflowTemplate(
    template_id="kenya_retail_booking",
    name="Kenya Retail Booking",
    industry=VerticalIndustry.RETAIL,
    description="Appointment booking with WhatsApp confirmation and escalation.",
    default_locale="mixed",
    supported_locales=("en", "sw", "mixed"),
    entry_step_id="greeting",
    integrations=IntegrationBindings(
        mpesa=False,
        whatsapp=True,
        call_routing=True,
        kenyan_intent=True,
    ),
    steps=(
        WorkflowStep(
            step_id="greeting",
            name="Greeting",
            kind=WorkflowStepKind.GREETING,
            next_step_id="booking",
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Welcome customers to the retail booking line. Ask how you can help.",
                },
            ),
        ),
        WorkflowStep(
            step_id="booking",
            name="Booking",
            kind=WorkflowStepKind.BOOKING,
            next_step_id="closing",
            rules=(
                BusinessRule(
                    rule_id="booking_confirmed",
                    name="Send WhatsApp confirmation",
                    when=RuleCondition("booking_confirmed", RuleOperator.EQ, True),
                    then=(
                        RuleAction(
                            RuleActionType.SEND_WHATSAPP,
                            {"template": "booking_confirmation"},
                        ),
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "closing"}),
                    ),
                    priority=10,
                ),
                _escalate_rule("booking_escalation", intent="escalation"),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={
                    "mixed": "Collect date, time, and service type. Confirm booking details before sending WhatsApp.",
                },
            ),
        ),
        WorkflowStep(
            step_id="closing",
            name="Closing",
            kind=WorkflowStepKind.CLOSING,
            rules=(
                BusinessRule(
                    rule_id="end_booking",
                    name="End workflow",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(RuleAction(RuleActionType.END_WORKFLOW, {}),),
                    priority=1,
                ),
            ),
            prompts=MultilingualPrompt(
                default_locale="mixed",
                system={"mixed": "Thank the customer and recap the booking."},
            ),
        ),
    ),
)


GENERAL_CUSTOMER_SUPPORT = VerticalWorkflowTemplate(
    template_id="general_customer_support",
    name="General Customer Support",
    industry=VerticalIndustry.GENERAL,
    description="Multilingual support with optional escalation.",
    default_locale="en",
    supported_locales=("en", "sw", "fr"),
    entry_step_id="greeting",
    integrations=IntegrationBindings(call_routing=True),
    steps=(
        WorkflowStep(
            step_id="greeting",
            name="Greeting",
            kind=WorkflowStepKind.GREETING,
            next_step_id="support",
            prompts=MultilingualPrompt(
                default_locale="en",
                system={"en": "You are a friendly customer support agent."},
            ),
        ),
        WorkflowStep(
            step_id="support",
            name="Support",
            kind=WorkflowStepKind.SUPPORT,
            next_step_id="closing",
            rules=(_escalate_rule("general_escalation", intent="escalation"),),
            prompts=MultilingualPrompt(
                default_locale="en",
                system={"en": "Answer questions and resolve issues. Escalate when needed."},
            ),
        ),
        WorkflowStep(
            step_id="closing",
            name="Closing",
            kind=WorkflowStepKind.CLOSING,
            rules=(
                BusinessRule(
                    rule_id="end_general",
                    name="End workflow",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(RuleAction(RuleActionType.END_WORKFLOW, {}),),
                    priority=1,
                ),
            ),
            prompts=MultilingualPrompt(
                default_locale="en",
                system={"en": "Close the conversation politely."},
            ),
        ),
    ),
)


BUILTIN_TEMPLATES: tuple[VerticalWorkflowTemplate, ...] = (
    KENYA_FINTECH_SUPPORT,
    KENYA_RETAIL_BOOKING,
    GENERAL_CUSTOMER_SUPPORT,
    *KENYA_MARKETPLACE_TEMPLATES,
)
