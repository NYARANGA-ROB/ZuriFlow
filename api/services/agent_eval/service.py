"""Orchestrate synthetic suites, version comparison, and gated production sampling."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.constants import AGENT_EVAL_ENABLED
from api.db import db_client
from api.services.agent_eval.catalog import catalog, get_scenario
from api.services.agent_eval.scoring import (
    aggregate_scores,
    compare_versions,
    evaluate_scenario,
)
from api.services.agent_eval.simulator import run_scenario
from api.services.kenyan_continuous_learning.anonymizer import (
    anonymize_turns,
    hash_run_reference,
)


class AgentEvalService:
    def status(self) -> dict[str, Any]:
        cats = sorted({s.category.value for s in catalog()})
        return {
            "enabled": AGENT_EVAL_ENABLED,
            "scenario_count": len(catalog()),
            "categories": cats,
            "pillars": ["accuracy", "safety", "latency", "completion", "customer_experience"],
            "training_policy": (
                "Production samples are evaluation-only. Training eligibility requires "
                "explicit consent plus a governance confirmation. Raw customer "
                "conversations are never used to train automatically."
            ),
        }

    def list_scenarios(self) -> list[dict[str, Any]]:
        return [
            {
                "id": s.id,
                "category": s.category.value,
                "title": s.title,
                "user_turns": s.user_turns,
                "expected": s.expected_dict(),
                "notes": s.notes,
            }
            for s in catalog()
        ]

    async def run_suite(
        self,
        *,
        organization_id: int,
        workflow_id: int | None = None,
        workflow_definition_id: int | None = None,
        scenario_ids: list[str] | None = None,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        workflow_json = None
        baseline = None
        if workflow_id:
            wf = await db_client.get_workflow(
                workflow_id, organization_id=organization_id
            )
            if wf is None:
                raise ValueError("Workflow not found")
            workflow_json = wf.workflow_definition or {}
            if workflow_definition_id is None:
                workflow_definition_id = getattr(wf, "released_definition_id", None)
            baseline = await db_client.get_previous_archived_definition(
                workflow_id,
                organization_id=organization_id,
                current_definition_id=workflow_definition_id,
            )

        scenarios = catalog()
        if scenario_ids:
            wanted = set(scenario_ids)
            scenarios = [s for s in scenarios if s.id in wanted]
        results = []
        evaluations = []
        for scenario in scenarios:
            raw = run_scenario(
                scenario,
                organization_id=organization_id,
                workflow_json=workflow_json,
            )
            evaluation = evaluate_scenario(scenario, raw)
            evaluations.append(evaluation)
            results.append({**raw, "evaluation": evaluation, "passed": evaluation["passed"]})

        score = aggregate_scores(evaluations)
        previous_score = None
        if workflow_id:
            prior_runs = await db_client.list_eval_runs(
                organization_id, workflow_id=workflow_id, limit=5
            )
            for prior in prior_runs:
                if prior.workflow_definition_id != workflow_definition_id and prior.score_json:
                    previous_score = prior.score_json
                    break
        comparison = compare_versions(previous_score, score)

        run = await db_client.create_eval_run(
            organization_id=organization_id,
            workflow_id=workflow_id,
            workflow_definition_id=workflow_definition_id,
            baseline_definition_id=getattr(baseline, "id", None),
            trigger=trigger,
            status="completed",
            scenario_filter=",".join(scenario_ids) if scenario_ids else None,
            score_json=score,
            comparison_json=comparison,
            metrics_json=score["metrics"],
        )
        persisted = []
        for item in results:
            row = await db_client.add_eval_result(
                organization_id=organization_id,
                run_id=run.id,
                scenario_id=item["scenario_id"],
                category=item["category"],
                passed=item["passed"],
                expected_json=item["expected"],
                actual_json=item["actual"],
                evaluation_json=item["evaluation"],
                transcript_json=item["transcript"],
                tool_calls_json=item["tool_calls"],
                workflow_path_json=item["workflow_path"],
                latency_ms=item.get("latency_ms"),
            )
            persisted.append(self._result_dict(row, title=item.get("title")))

        return {
            "run": self._run_dict(run),
            "results": persisted,
            "score": score,
            "comparison": comparison,
        }

    async def rerun_failed(
        self, run_id: int, *, organization_id: int
    ) -> dict[str, Any]:
        parent = await db_client.get_eval_run(run_id, organization_id=organization_id)
        if parent is None:
            raise ValueError("Eval run not found")
        rows = await db_client.list_eval_results(run_id, organization_id=organization_id)
        failed_ids = [r.scenario_id for r in rows if not r.passed]
        if not failed_ids:
            return await self.get_run(run_id, organization_id=organization_id)
        return await self.run_suite(
            organization_id=organization_id,
            workflow_id=parent.workflow_id,
            workflow_definition_id=parent.workflow_definition_id,
            scenario_ids=failed_ids,
            trigger="rerun_failed",
        )

    async def rerun_scenario(
        self, scenario_id: str, *, organization_id: int, workflow_id: int | None
    ) -> dict[str, Any]:
        if get_scenario(scenario_id) is None:
            raise ValueError("Unknown scenario")
        return await self.run_suite(
            organization_id=organization_id,
            workflow_id=workflow_id,
            scenario_ids=[scenario_id],
            trigger="rerun_scenario",
        )

    async def get_run(self, run_id: int, *, organization_id: int) -> dict[str, Any]:
        run = await db_client.get_eval_run(run_id, organization_id=organization_id)
        if run is None:
            raise ValueError("Eval run not found")
        rows = await db_client.list_eval_results(run_id, organization_id=organization_id)
        return {
            "run": self._run_dict(run),
            "results": [self._result_dict(r) for r in rows],
            "score": run.score_json,
            "comparison": run.comparison_json,
        }

    async def list_runs(
        self, organization_id: int, *, workflow_id: int | None = None
    ) -> list[dict[str, Any]]:
        rows = await db_client.list_eval_runs(
            organization_id, workflow_id=workflow_id, limit=50
        )
        return [self._run_dict(r) for r in rows]

    async def sample_production_run(
        self,
        *,
        organization_id: int,
        workflow_run_id: int,
        consent_ok: bool,
    ) -> dict[str, Any]:
        if not consent_ok:
            raise ValueError("Refusing to sample production conversation without consent")
        run = await db_client.get_workflow_run_by_id(workflow_run_id)
        org = await db_client.get_organization_id_by_workflow_run_id(workflow_run_id)
        if run is None or org != organization_id:
            raise ValueError("Run not found")
        turns = _turns_from_run(run)
        sample = await db_client.insert_production_sample(
            organization_id=organization_id,
            workflow_id=getattr(run, "workflow_id", None),
            run_reference_hash=hash_run_reference(workflow_run_id, organization_id),
            consent_ok=True,
            anonymized_turns=anonymize_turns(turns),
            training_eligible=False,
            governance_note="Sampled for evaluation only. Training disabled.",
        )
        return self._sample_dict(sample)

    async def list_production_samples(self, organization_id: int) -> list[dict[str, Any]]:
        rows = await db_client.list_production_samples(organization_id)
        return [self._sample_dict(r) for r in rows]

    async def set_training_eligible(
        self,
        sample_id: int,
        *,
        organization_id: int,
        eligible: bool,
        confirmation: str,
    ) -> dict[str, Any]:
        if eligible and confirmation.strip().upper() != "ALLOW_TRAINING":
            raise ValueError("Explicit governance confirmation ALLOW_TRAINING is required")
        row = await db_client.set_training_eligible(
            sample_id,
            organization_id=organization_id,
            eligible=eligible,
            governance_note="Marked by administrator with explicit confirmation"
            if eligible
            else "Training eligibility revoked",
        )
        if row is None:
            raise ValueError("Sample not found")
        return self._sample_dict(row)

    def _run_dict(self, row: Any) -> dict[str, Any]:
        return {
            "id": row.id,
            "organization_id": row.organization_id,
            "workflow_id": row.workflow_id,
            "workflow_definition_id": row.workflow_definition_id,
            "baseline_definition_id": row.baseline_definition_id,
            "trigger": row.trigger,
            "status": row.status,
            "score": row.score_json,
            "comparison": row.comparison_json,
            "metrics": row.metrics_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _result_dict(self, row: Any, title: str | None = None) -> dict[str, Any]:
        scenario = get_scenario(row.scenario_id)
        return {
            "id": row.id,
            "run_id": row.run_id,
            "scenario_id": row.scenario_id,
            "title": title or (scenario.title if scenario else row.scenario_id),
            "category": row.category,
            "passed": row.passed,
            "expected": row.expected_json,
            "actual": row.actual_json,
            "evaluation": row.evaluation_json,
            "transcript": row.transcript_json,
            "tool_calls": row.tool_calls_json,
            "workflow_path": row.workflow_path_json,
            "latency_ms": row.latency_ms,
        }

    def _sample_dict(self, row: Any) -> dict[str, Any]:
        return {
            "id": row.id,
            "organization_id": row.organization_id,
            "workflow_id": row.workflow_id,
            "run_reference_hash": row.run_reference_hash,
            "consent_ok": row.consent_ok,
            "anonymized_turns": row.anonymized_turns,
            "training_eligible": row.training_eligible,
            "governance_note": row.governance_note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


_SERVICE: AgentEvalService | None = None


def get_agent_eval_service() -> AgentEvalService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AgentEvalService()
    return _SERVICE


def _turns_from_run(run: Any) -> list[dict[str, str]]:
    logs = getattr(run, "logs", None) or {}
    events = logs.get("realtime_feedback_events") or []
    turns = []
    for event in events:
        payload = event.get("payload") or {}
        text = payload.get("text")
        if not text:
            continue
        role = "user" if "USER" in str(event.get("type", "")).upper() else "assistant"
        turns.append({"role": role, "text": str(text)})
    if not turns:
        ctx = getattr(run, "gathered_context", None) or {}
        transcript = ctx.get("transcript")
        if isinstance(transcript, str):
            turns = [{"role": "unknown", "text": transcript[:2000]}]
    return turns[:40]


async def enqueue_eval_on_publish(
    *, organization_id: int, workflow_id: int, definition_id: int
) -> None:
    if not AGENT_EVAL_ENABLED:
        return
    try:
        from api.tasks.arq import enqueue_job
        from api.tasks.function_names import FunctionNames

        await enqueue_job(
            FunctionNames.RUN_AGENT_EVAL_SUITE,
            organization_id,
            workflow_id,
            definition_id,
        )
    except Exception as exc:
        logger.warning("agent eval enqueue failed: {}", exc)
