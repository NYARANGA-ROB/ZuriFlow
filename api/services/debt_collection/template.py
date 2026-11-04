"""Kenyan debt collection vertical workflow template."""

from __future__ import annotations

from api.services.debt_collection.prompts import (
    CLOSING_PROMPT,
    ESCALATION_PROMPT,
    GREETING_PROMPT,
    INSTALLMENT_PROMPT,
    MPESA_PROMPT,
    NEGOTIATION_PROMPT,
    VERIFY_PROMPT,
)
from api.services.vertical_workflows.schema import (
    BusinessRule,
    IntegrationBindings,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleOperator,
    VerticalIndustry,
    VerticalWorkflowTemplate,
    WorkflowStep,
    WorkflowStepKind,
)

KENYA_DEBT_COLLECTION = VerticalWorkflowTemplate(
    template_id="kenya_debt_collection",
    name="Kenya Debt Collection",
    industry=VerticalIndustry.DEBT_COLLECTION,
    description=(
        "Polite multilingual debt collection with payment negotiation, installment "
        "scheduling, M-Pesa, escalation, and commitment tracking."
    ),
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
            rule_id="escalate_high_risk",
            name="Escalate high-risk conversation",
            when=RuleCondition("escalation_risk", RuleOperator.IN, ["high", "critical"]),
            then=(
                RuleAction(RuleActionType.ESCALATE, {"reason": "debt_risk"}),
                RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "escalation"}),
            ),
            priority=5,
        ),
        BusinessRule(
            rule_id="track_interruption",
            name="Acknowledge interruption",
            when=RuleCondition("interrupted", RuleOperator.EQ, True),
            then=(
                RuleAction(RuleActionType.SET_VARIABLE, {"interruption_ack": True}),
            ),
            priority=8,
        ),
        BusinessRule(
            rule_id="escalate_customer_request",
            name="Customer requests human",
            when=RuleCondition("intent", RuleOperator.INTENT_IS, "escalation"),
            then=(
                RuleAction(RuleActionType.ESCALATE, {"reason": "customer_request"}),
                RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "escalation"}),
            ),
            priority=6,
        ),
    ),
    steps=(
        WorkflowStep(
            step_id="greeting",
            name="Greeting & Identity",
            kind=WorkflowStepKind.GREETING,
            next_step_id="verify",
            prompts=GREETING_PROMPT,
        ),
        WorkflowStep(
            step_id="verify",
            name="Verify Account",
            kind=WorkflowStepKind.QUALIFY,
            next_step_id="negotiation",
            prompts=VERIFY_PROMPT,
            rules=(
                BusinessRule(
                    rule_id="skip_to_negotiation",
                    name="Identity confirmed",
                    when=RuleCondition("identity_confirmed", RuleOperator.EQ, True),
                    then=(RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "negotiation"}),),
                    priority=20,
                ),
            ),
        ),
        WorkflowStep(
            step_id="negotiation",
            name="Payment Negotiation",
            kind=WorkflowStepKind.NEGOTIATION,
            next_step_id="installment",
            prompts=NEGOTIATION_PROMPT,
            rules=(
                BusinessRule(
                    rule_id="full_payment_intent",
                    name="Customer agrees full payment",
                    when=RuleCondition("negotiation_outcome", RuleOperator.EQ, "full_payment"),
                    then=(
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "collect_payment"}),
                    ),
                    priority=15,
                ),
                BusinessRule(
                    rule_id="installment_intent",
                    name="Installment plan agreed",
                    when=RuleCondition("negotiation_outcome", RuleOperator.EQ, "installment_plan"),
                    then=(
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "installment"}),
                    ),
                    priority=16,
                ),
                BusinessRule(
                    rule_id="partial_commitment",
                    name="Partial payment commitment",
                    when=RuleCondition("negotiation_outcome", RuleOperator.EQ, "partial_commitment"),
                    then=(
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "collect_payment"}),
                    ),
                    priority=17,
                ),
                BusinessRule(
                    rule_id="customer_offer_amount",
                    name="Customer proposed amount",
                    when=RuleCondition("customer_offer_amount", RuleOperator.GT, 0),
                    then=(
                        RuleAction(RuleActionType.SET_VARIABLE, {"evaluate_offer": True}),
                    ),
                    priority=25,
                ),
            ),
        ),
        WorkflowStep(
            step_id="installment",
            name="Installment Schedule",
            kind=WorkflowStepKind.INSTALLMENT,
            next_step_id="collect_payment",
            prompts=INSTALLMENT_PROMPT,
            rules=(
                BusinessRule(
                    rule_id="plan_approved",
                    name="Installment plan approved",
                    when=RuleCondition("installment_plan_approved", RuleOperator.EQ, True),
                    then=(
                        RuleAction(
                            RuleActionType.SEND_WHATSAPP,
                            {"template": "installment_schedule"},
                        ),
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "collect_payment"}),
                    ),
                    priority=10,
                ),
            ),
        ),
        WorkflowStep(
            step_id="collect_payment",
            name="M-Pesa Collection",
            kind=WorkflowStepKind.COLLECT_PAYMENT,
            next_step_id="closing",
            prompts=MPESA_PROMPT,
            rules=(
                BusinessRule(
                    rule_id="request_mpesa",
                    name="Trigger M-Pesa STK",
                    when=RuleCondition("payment_amount", RuleOperator.GT, 0),
                    then=(
                        RuleAction(RuleActionType.REQUEST_PAYMENT, {}),
                    ),
                    priority=10,
                ),
                BusinessRule(
                    rule_id="payment_success",
                    name="Payment collected",
                    when=RuleCondition("payment_status", RuleOperator.EQ, "success"),
                    then=(
                        RuleAction(RuleActionType.SET_VARIABLE, {"commitment_fulfilled": True}),
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "closing"}),
                    ),
                    priority=5,
                ),
                BusinessRule(
                    rule_id="payment_failed_escalate",
                    name="Payment failed twice",
                    when=RuleCondition("payment_failures", RuleOperator.GTE, 2),
                    then=(
                        RuleAction(RuleActionType.ESCALATE, {"reason": "payment_failed"}),
                        RuleAction(RuleActionType.ADVANCE_STEP, {"step_id": "escalation"}),
                    ),
                    priority=8,
                ),
            ),
        ),
        WorkflowStep(
            step_id="escalation",
            name="Human Escalation",
            kind=WorkflowStepKind.ESCALATION,
            next_step_id="closing",
            prompts=ESCALATION_PROMPT,
            rules=(
                BusinessRule(
                    rule_id="route_supervisor",
                    name="Route to collections supervisor",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(
                        RuleAction(
                            RuleActionType.ROUTE_QUEUE,
                            {"queue": "collections_supervisor"},
                        ),
                    ),
                    priority=1,
                ),
            ),
        ),
        WorkflowStep(
            step_id="closing",
            name="Closing",
            kind=WorkflowStepKind.CLOSING,
            prompts=CLOSING_PROMPT,
            rules=(
                BusinessRule(
                    rule_id="end_collection",
                    name="End workflow",
                    when=RuleCondition("field", RuleOperator.ALWAYS),
                    then=(RuleAction(RuleActionType.END_WORKFLOW, {}),),
                    priority=1,
                ),
            ),
        ),
    ),
    metadata={
        "region": "KE",
        "compliance": ["cbk_fair_debt_collection", "no_threats"],
        "goals": ["maximize_repayment", "minimize_frustration", "escalate_risk"],
    },
)
