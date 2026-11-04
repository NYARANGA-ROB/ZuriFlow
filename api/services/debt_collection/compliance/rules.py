"""Compliance rule engine for debt collection conversations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from api.services.debt_collection.compliance.types import (
    ComplianceViolation,
    ComplianceViolationType,
    SpeakerRole,
    ViolationSeverity,
)

# Agent-side: illegal or misleading threats (CBK fair debt collection).
AGENT_ILLEGAL_THREAT = re.compile(
    r"\b("
    r"arrest you|go to jail|send police|police will come|"
    r"seize your (house|property|assets|car)|auction your|"
    r"blacklist you forever|ruin your credit forever|"
    r"publish your name|name and shame|embarrass you|"
    r"garnish your salary without|take your children|"
    r"kufungwa gerezani|polisi watakuja|tutachukua nyumba|"
    r"tutaauza mali|tutaonyesha jina lako"
    r")\b",
    re.IGNORECASE,
)

AGENT_ABUSIVE = re.compile(
    r"\b("
    r"stupid|idiot|lazy|deadbeat|thief|conman|fraud|shut up|"
    r"mpumbavu|mjinga|mwizi|malaya|msenge"
    r")\b",
    re.IGNORECASE,
)

AGENT_AGGRESSIVE_NEGOTIATION = re.compile(
    r"\b("
    r"pay now or else|final warning|last chance|no excuses|"
    r"you have no choice|must pay today|non.?negotiable|"
    r"we will not wait|pay immediately or|"
    r"lipa sasa au|onyo la mwisho|hakuna chaguo"
    r")\b",
    re.IGNORECASE,
)

AGENT_HARASSMENT = re.compile(
    r"\b("
    r"call you every day|call your boss|call your family|"
    r"won't stop calling|harass|"
    r"tutapiga simu kila siku|tutaambia bosi wako"
    r")\b",
    re.IGNORECASE,
)

# Ultimatum without offering an alternative violates polite negotiation policy.
AGENT_ULTIMATUM = re.compile(
    r"\b(pay in full today|full amount today|no payment plan|no installment)\b",
    re.IGNORECASE,
)

POLITE_ALTERNATIVE = re.compile(
    r"\b("
    r"installment|payment plan|partial|option|alternative|"
    r"work with you|flexible|arrangement|plan|"
    r"mpango|awamu|chaguo|tunaweza kufanya"
    r")\b",
    re.IGNORECASE,
)

# Customer-side signals (escalation, not blocking).
CUSTOMER_ABUSIVE = re.compile(
    r"\b(stupid|idiot|thief|conman|fraud|shut up|go away|nonsense|"
    r"mpumbavu|mjinga|mwizi|malaya)\b",
    re.IGNORECASE,
)

CUSTOMER_LEGAL_THREAT = re.compile(
    r"\b(lawyer|sue|court|police|report you|ombudsman|central bank|"
    r"wakili|mahakama|polisi|barua ya wakili)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    pattern: re.Pattern[str]
    violation_type: ComplianceViolationType
    severity: ViolationSeverity
    speaker: SpeakerRole
    message: str
    requires_no_alternative: bool = False


_AGENT_RULES: tuple[_Rule, ...] = (
    _Rule(
        "agent_illegal_threat",
        AGENT_ILLEGAL_THREAT,
        ComplianceViolationType.ILLEGAL_THREAT,
        ViolationSeverity.BLOCK,
        SpeakerRole.AGENT,
        "Agent output contained an illegal or misleading threat.",
    ),
    _Rule(
        "agent_abusive",
        AGENT_ABUSIVE,
        ComplianceViolationType.ABUSIVE_LANGUAGE,
        ViolationSeverity.BLOCK,
        SpeakerRole.AGENT,
        "Agent used abusive or demeaning language.",
    ),
    _Rule(
        "agent_aggressive_negotiation",
        AGENT_AGGRESSIVE_NEGOTIATION,
        ComplianceViolationType.AGGRESSIVE_NEGOTIATION,
        ViolationSeverity.BLOCK,
        SpeakerRole.AGENT,
        "Agent used coercive negotiation language.",
    ),
    _Rule(
        "agent_harassment",
        AGENT_HARASSMENT,
        ComplianceViolationType.HARASSMENT,
        ViolationSeverity.BLOCK,
        SpeakerRole.AGENT,
        "Agent implied harassment or improper contact.",
    ),
    _Rule(
        "agent_ultimatum_no_alternative",
        AGENT_ULTIMATUM,
        ComplianceViolationType.MISSING_POLITE_ALTERNATIVE,
        ViolationSeverity.WARN,
        SpeakerRole.AGENT,
        "Agent demanded payment without offering alternatives.",
        requires_no_alternative=True,
    ),
)

_CUSTOMER_RULES: tuple[_Rule, ...] = (
    _Rule(
        "customer_abusive",
        CUSTOMER_ABUSIVE,
        ComplianceViolationType.CUSTOMER_ABUSIVE,
        ViolationSeverity.CRITICAL,
        SpeakerRole.CUSTOMER,
        "Customer used abusive language.",
    ),
    _Rule(
        "customer_legal_threat",
        CUSTOMER_LEGAL_THREAT,
        ComplianceViolationType.CUSTOMER_LEGAL_THREAT,
        ViolationSeverity.CRITICAL,
        SpeakerRole.CUSTOMER,
        "Customer referenced legal or regulatory action.",
    ),
)


class ComplianceRuleEngine:
    """Evaluate transcript text against debt collection compliance rules."""

    def evaluate(self, text: str, *, speaker: SpeakerRole) -> list[ComplianceViolation]:
        if not text.strip():
            return []

        rules = _AGENT_RULES if speaker == SpeakerRole.AGENT else _CUSTOMER_RULES
        violations: list[ComplianceViolation] = []
        has_alternative = bool(POLITE_ALTERNATIVE.search(text))

        for rule in rules:
            match = rule.pattern.search(text)
            if not match:
                continue
            if rule.requires_no_alternative and has_alternative:
                continue
            violations.append(
                ComplianceViolation(
                    violation_type=rule.violation_type,
                    severity=rule.severity,
                    rule_id=rule.rule_id,
                    matched_pattern=match.group(0),
                    speaker=speaker,
                    message=rule.message,
                )
            )
        return violations

    def highest_severity(
        self, violations: list[ComplianceViolation]
    ) -> ViolationSeverity | None:
        order = (
            ViolationSeverity.WARN,
            ViolationSeverity.BLOCK,
            ViolationSeverity.CRITICAL,
        )
        if not violations:
            return None
        return max(violations, key=lambda v: order.index(v.severity)).severity


_engine: ComplianceRuleEngine | None = None


def get_compliance_rule_engine() -> ComplianceRuleEngine:
    global _engine
    if _engine is None:
        _engine = ComplianceRuleEngine()
    return _engine
