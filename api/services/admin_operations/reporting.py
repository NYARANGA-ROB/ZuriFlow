"""Report export for admin operations."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


def export_summary_json(summary: dict[str, Any]) -> tuple[io.BytesIO, str]:
    payload = json.dumps(summary, indent=2, default=str).encode("utf-8")
    buf = io.BytesIO(payload)
    org_id = summary.get("organization_id", "org")
    filename = f"admin_ops_summary_{org_id}.json"
    return buf, filename


def export_summary_csv(summary: dict[str, Any]) -> tuple[io.StringIO, str]:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "metric", "value"])

    org_id = summary.get("organization_id")
    writer.writerow(["meta", "organization_id", org_id])
    writer.writerow(["meta", "from_ts", summary.get("from_ts")])
    writer.writerow(["meta", "to_ts", summary.get("to_ts")])

    live = summary.get("live_calls") or {}
    writer.writerow(["live_calls", "active_audio_sessions", live.get("active_audio_sessions")])
    writer.writerow(
        ["live_calls", "incomplete_workflow_runs", live.get("incomplete_workflow_runs")]
    )

    payments = summary.get("payments") or {}
    mpesa = payments.get("mpesa") or {}
    writer.writerow(["payments", "transaction_count", mpesa.get("transaction_count")])
    writer.writerow(["payments", "collected_amount", mpesa.get("collected_amount")])

    workflows = summary.get("workflow_performance") or {}
    writer.writerow(["workflows", "total_runs", workflows.get("total_runs")])
    writer.writerow(["workflows", "completion_rate", workflows.get("completion_rate")])

    tenant = summary.get("tenant") or {}
    writer.writerow(["tenant", "total_calls", tenant.get("total_calls")])
    writer.writerow(["tenant", "member_count", tenant.get("member_count")])
    writer.writerow(["tenant", "active_workflows", tenant.get("active_workflows")])

    campaigns = summary.get("campaigns") or {}
    writer.writerow(["campaigns", "total", campaigns.get("total")])

    filename = f"admin_ops_summary_{org_id}.csv"
    return buf, filename
