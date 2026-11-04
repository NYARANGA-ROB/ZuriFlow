"""Agent evaluation catalog, policy, scoring, and governance."""

from __future__ import annotations

from api.services.agent_eval.catalog import catalog, get_scenario, required_categories
from api.services.agent_eval.policy import decide_policy
from api.services.agent_eval.scoring import aggregate_scores, compare_versions, evaluate_scenario
from api.services.agent_eval.simulator import run_scenario
from api.services.agent_eval.types import Scenario


def test_catalog_covers_required_categories():
    cats = {s.category.value for s in catalog()}
    assert required_categories() <= cats
    assert len(catalog()) >= 15


def test_prompt_injection_refuses_tools():
    scenario = get_scenario("prompt-injection")
    result = run_scenario(scenario, organization_id=1, workflow_json={})
    evaluation = evaluate_scenario(scenario, result)
    assert result["actual"]["refuse_injection"] is True
    assert result["tool_calls"] == []
    assert evaluation["checks"]["prompt_injection"]
    assert evaluation["passed"]


def test_failed_payment_does_not_confirm():
    scenario = get_scenario("payment-failed")
    result = run_scenario(scenario, organization_id=1, workflow_json={})
    evaluation = evaluate_scenario(scenario, result)
    assert "confirm_payment" not in result["actual"]["tools"]
    assert result["actual"]["payment_success_claim"] is False
    assert evaluation["checks"]["payment_safety"]
    assert evaluation["checks"]["hallucination_free"]


def test_invalid_phone_does_not_send_stk():
    scenario = get_scenario("invalid-phone")
    result = run_scenario(scenario, organization_id=1, workflow_json={})
    assert "stk_push" not in result["actual"]["tools"]
    evaluation = evaluate_scenario(scenario, result)
    assert evaluation["checks"]["payment_safety"]


def test_interruption_marks_barge_in():
    scenario = get_scenario("barge-in-mid-tts")
    result = run_scenario(scenario, organization_id=1, workflow_json={})
    assert result["actual"]["barge_in_handled"] is True
    assert evaluate_scenario(scenario, result)["checks"]["interruption"]


def test_malicious_exfil_no_tools():
    scenario = get_scenario("malicious-exfil")
    result = run_scenario(scenario, organization_id=1, workflow_json={})
    assert result["actual"]["refuse_injection"] is True
    assert evaluate_scenario(scenario, result)["passed"]


def test_pillars_are_not_a_single_opaque_number():
    scenario = get_scenario("prompt-injection")
    result = run_scenario(scenario, organization_id=1, workflow_json={})
    ev = evaluate_scenario(scenario, result)
    score = aggregate_scores([ev])
    for pillar in ("accuracy", "safety", "latency", "completion", "customer_experience"):
        assert pillar in score["pillars"]
    assert "intent_accuracy" in score["metrics"]
    assert "sla" in score["note"].lower()


def test_version_comparison_flags_regression():
    previous = {
        "pillars": {
            "accuracy": 90,
            "safety": 90,
            "latency": 80,
            "completion": 85,
            "customer_experience": 80,
        }
    }
    current = {
        "pillars": {
            "accuracy": 70,
            "safety": 90,
            "latency": 80,
            "completion": 85,
            "customer_experience": 80,
        }
    }
    cmp = compare_versions(previous, current)
    assert cmp["has_baseline"]
    assert "accuracy" in cmp["regressed_pillars"]
    assert cmp["deltas"]["accuracy"]["previous"] == 90
    assert cmp["deltas"]["accuracy"]["new"] == 70


def test_training_never_enabled_by_policy_helper():
    policy = decide_policy(
        ["Hello"],
        intent="support",
        entities={},
        interruption=False,
        expect_escalate=False,
    )
    assert "training" not in policy


def test_workflow_path_matches_node_labels():
    scenario = get_scenario("code-switch-pay")
    graph = {
        "nodes": [
            {"id": "1", "data": {"name": "Collect payment via M-Pesa"}},
        ]
    }
    result = run_scenario(scenario, organization_id=1, workflow_json=graph)
    assert result["workflow_path"]
    dummy = Scenario(
        id="x",
        category=scenario.category,
        title="x",
        user_turns=scenario.user_turns,
        expected_tools=[],
        forbidden_tools=["confirm_payment"],
        expected_workflow_nodes=["payment"],
    )
    ev = evaluate_scenario(dummy, result)
    assert ev["checks"]["workflow_completion"]
