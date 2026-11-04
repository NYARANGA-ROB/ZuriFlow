"""Types for the ZuriFlow agent evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScenarioCategory(str, Enum):
    NORMAL = "normal_customers"
    CONFUSED = "confused_customers"
    ANGRY = "angry_customers"
    CODE_SWITCHING = "code_switching"
    SHENG = "sheng"
    KISWAHILI = "kiswahili"
    ENGLISH = "english"
    PAYMENT_REQUEST = "payment_requests"
    FAILED_PAYMENT = "failed_payments"
    INTERRUPTION = "interruptions"
    AMBIGUOUS = "ambiguous_requests"
    HUMAN_ESCALATION = "human_escalation"
    MALICIOUS = "malicious_instructions"
    PROMPT_INJECTION = "prompt_injection"
    INVALID_INFORMATION = "invalid_information"


SCORE_PILLARS = ("accuracy", "safety", "latency", "completion", "customer_experience")


@dataclass
class Scenario:
    id: str
    category: ScenarioCategory
    title: str
    user_turns: list[str]
    interruption: bool = False
    expected_intent: str | None = None
    expected_intent_any: tuple[str, ...] = ()
    expected_language_any: tuple[str, ...] = ()
    expected_entities: dict[str, Any] = field(default_factory=dict)
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expected_workflow_nodes: list[str] = field(default_factory=list)
    expect_escalate: bool = False
    expect_refuse_injection: bool = False
    expect_payment_success_claim: bool = False
    expect_clarify: bool = False
    notes: str = ""

    def expected_dict(self) -> dict[str, Any]:
        return {
            "intent": self.expected_intent,
            "intent_any": list(self.expected_intent_any),
            "language_any": list(self.expected_language_any),
            "entities": self.expected_entities,
            "tools": self.expected_tools,
            "forbidden_tools": self.forbidden_tools,
            "workflow_nodes": self.expected_workflow_nodes,
            "escalate": self.expect_escalate,
            "refuse_injection": self.expect_refuse_injection,
            "payment_success_claim": self.expect_payment_success_claim,
            "clarify": self.expect_clarify,
            "interruption": self.interruption,
        }
