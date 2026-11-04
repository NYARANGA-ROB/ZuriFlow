"""Business rule evaluation engine for vertical workflows."""

from __future__ import annotations

from typing import Any

from api.services.vertical_workflows.schema import (
    BusinessRule,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleOperator,
)


def _resolve_field(context: dict[str, Any], field: str) -> Any:
    if field == "field":
        return True
    parts = field.split(".")
    cur: Any = context
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def evaluate_condition(condition: RuleCondition, context: dict[str, Any]) -> bool:
    if condition.operator == RuleOperator.ALWAYS:
        return True

    actual = _resolve_field(context, condition.field)
    expected = condition.value

    match condition.operator:
        case RuleOperator.EQ:
            return actual == expected
        case RuleOperator.NE:
            return actual != expected
        case RuleOperator.GT:
            return actual is not None and actual > expected
        case RuleOperator.GTE:
            return actual is not None and actual >= expected
        case RuleOperator.LT:
            return actual is not None and actual < expected
        case RuleOperator.LTE:
            return actual is not None and actual <= expected
        case RuleOperator.CONTAINS:
            if actual is None:
                return False
            return str(expected).lower() in str(actual).lower()
        case RuleOperator.IN:
            if not isinstance(expected, (list, tuple, set)):
                return False
            return actual in expected
        case RuleOperator.INTENT_IS:
            intent = context.get("intent") or _resolve_field(context, "intent.name")
            return str(intent) == str(expected)
        case RuleOperator.LANGUAGE_IN:
            lang = context.get("language") or context.get("locale")
            if not isinstance(expected, (list, tuple, set)):
                return False
            return str(lang) in {str(x) for x in expected}
    return False


class BusinessRuleEngine:
    """Evaluate ordered business rules against a workflow context."""

    def match_rules(
        self,
        rules: tuple[BusinessRule, ...],
        context: dict[str, Any],
    ) -> list[BusinessRule]:
        matched: list[BusinessRule] = []
        ordered = sorted(
            (r for r in rules if r.enabled),
            key=lambda r: r.priority,
        )
        for rule in ordered:
            if evaluate_condition(rule.when, context):
                matched.append(rule)
        return matched

    def evaluate(
        self,
        rules: tuple[BusinessRule, ...],
        context: dict[str, Any],
    ) -> list[RuleAction]:
        actions: list[RuleAction] = []
        for rule in self.match_rules(rules, context):
            actions.extend(rule.then)
        return actions

    def evaluate_single(
        self,
        rule: BusinessRule,
        context: dict[str, Any],
    ) -> list[RuleAction]:
        if not rule.enabled:
            return []
        if not evaluate_condition(rule.when, context):
            return []
        return list(rule.then)


_engine: BusinessRuleEngine | None = None


def get_business_rule_engine() -> BusinessRuleEngine:
    global _engine
    if _engine is None:
        _engine = BusinessRuleEngine()
    return _engine
