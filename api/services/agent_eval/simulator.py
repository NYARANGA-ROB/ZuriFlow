"""Run a synthetic scenario against Kenya NLU + workflow metadata + safety policy."""

from __future__ import annotations

import time
from typing import Any

from api.services.agent_eval.policy import decide_policy
from api.services.agent_eval.types import Scenario
from api.services.kenya.pipeline import process_kenya_turn


def extract_node_names(workflow_json: dict[str, Any] | None) -> list[str]:
    if not workflow_json:
        return []
    names: list[str] = []
    for node in workflow_json.get("nodes") or []:
        data = node.get("data") or {}
        label = data.get("name") or data.get("label") or node.get("id") or ""
        if label:
            names.append(str(label))
    return names


def match_workflow_path(expected_tokens: list[str], node_names: list[str]) -> list[str]:
    if not expected_tokens:
        return []
    if not node_names:
        return []
    hits = []
    lowered = [n.lower() for n in node_names]
    for token in expected_tokens:
        tok = token.lower()
        for name, raw in zip(lowered, node_names):
            if tok in name:
                hits.append(raw)
                break
    return hits


def run_scenario(
    scenario: Scenario,
    *,
    organization_id: int,
    workflow_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    last_intent = None
    last_language = None
    entities: dict[str, Any] = {}
    transcript: list[dict[str, str]] = []
    kenya_meta: dict[str, Any] = {}

    for i, turn in enumerate(scenario.user_turns):
        result = process_kenya_turn(
            turn,
            session_id=f"eval-{organization_id}-{scenario.id}",
            organization_id=organization_id,
        )
        transcript.append({"role": "user", "text": turn})
        if result.intent:
            last_intent = result.intent.intent.value if result.intent.intent else None
        last_language = result.language.primary_language.value
        safe = result.entities.to_safe_dict() if result.entities else {}
        for key, value in safe.items():
            if value:
                entities[key] = value
        kenya_meta = {
            "confidence": result.confidence.to_dict() if result.confidence else None,
            "escalation": result.escalation.to_dict() if result.escalation else None,
        }

    policy = decide_policy(
        scenario.user_turns,
        intent=last_intent,
        entities=entities,
        interruption=scenario.interruption,
        expect_escalate=scenario.expect_escalate,
    )
    transcript.append({"role": "assistant", "text": policy["agent_reply"]})

    node_names = extract_node_names(workflow_json)
    path = match_workflow_path(scenario.expected_workflow_nodes, node_names)
    if not node_names and scenario.expected_workflow_nodes:
        path = ["synthetic:" + scenario.expected_workflow_nodes[0]]

    latency_ms = (time.perf_counter() - started) * 1000.0
    actual = {
        "intent": last_intent,
        "language": last_language,
        "entities": {k: True for k in entities},
        "tools": policy["tools"],
        "escalate": policy["escalate"]
        or bool((kenya_meta.get("escalation") or {}).get("escalate")),
        "clarify": policy["clarify"],
        "refuse_injection": policy["refuse_injection"],
        "payment_success_claim": policy["claims_payment_success"],
        "barge_in_handled": policy["barge_in_handled"],
        "workflow_path": path,
        "latency_ms": round(latency_ms, 2),
        "kenya": kenya_meta,
        "turn_count": i + 1 if scenario.user_turns else 0,
    }
    return {
        "scenario_id": scenario.id,
        "category": scenario.category.value,
        "title": scenario.title,
        "transcript": transcript,
        "tool_calls": [{"name": t, "arguments": {}} for t in policy["tools"]],
        "workflow_path": path,
        "expected": scenario.expected_dict(),
        "actual": actual,
        "latency_ms": round(latency_ms, 2),
    }
