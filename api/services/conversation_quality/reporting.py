"""Automated reporting for conversation quality evaluations."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


def export_evaluation_json(evaluation: dict[str, Any]) -> tuple[io.BytesIO, str]:
    payload = json.dumps(evaluation, indent=2, default=str).encode("utf-8")
    run_id = evaluation.get("workflow_run_id", "run")
    return io.BytesIO(payload), f"conversation_quality_{run_id}.json"


def export_summary_csv(rows: list[dict[str, Any]]) -> tuple[io.StringIO, str]:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "workflow_run_id",
            "workflow_id",
            "overall_score",
            "response_quality",
            "interruption_handling",
            "payment_negotiation",
            "latency",
            "conversational_naturalness",
            "escalation_correctness",
            "regression_detected",
            "evaluated_at",
        ]
    )
    for row in rows:
        dims = row.get("dimensions") or {}
        writer.writerow(
            [
                row.get("workflow_run_id"),
                row.get("workflow_id"),
                row.get("overall_score"),
                _dim_score(dims, "response_quality"),
                _dim_score(dims, "interruption_handling"),
                _dim_score(dims, "payment_negotiation"),
                _dim_score(dims, "latency"),
                _dim_score(dims, "conversational_naturalness"),
                _dim_score(dims, "escalation_correctness"),
                (row.get("regression") or {}).get("regression_detected"),
                row.get("evaluated_at"),
            ]
        )
    org_id = rows[0].get("organization_id", "org") if rows else "org"
    return buf, f"conversation_quality_summary_{org_id}.csv"


def build_org_summary(
    *,
    organization_id: int,
    evaluations: list[dict[str, Any]],
    regressions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not evaluations:
        return {
            "organization_id": organization_id,
            "evaluation_count": 0,
            "avg_overall_score": None,
            "dimension_averages": {},
            "regression_count": 0,
        }

    overall = [e["overall_score"] for e in evaluations if e.get("overall_score") is not None]
    dim_sums: dict[str, list[float]] = {}
    for ev in evaluations:
        for key, data in (ev.get("dimensions") or {}).items():
            score = data.get("score") if isinstance(data, dict) else None
            if score is not None:
                dim_sums.setdefault(key, []).append(float(score))

    return {
        "organization_id": organization_id,
        "evaluation_count": len(evaluations),
        "avg_overall_score": round(sum(overall) / len(overall), 2) if overall else None,
        "dimension_averages": {
            k: round(sum(v) / len(v), 2) for k, v in dim_sums.items() if v
        },
        "regression_count": len(regressions),
        "recent_regressions": regressions[:10],
    }


def _dim_score(dims: dict, key: str) -> float | None:
    entry = dims.get(key)
    if isinstance(entry, dict):
        return entry.get("score")
    return None
