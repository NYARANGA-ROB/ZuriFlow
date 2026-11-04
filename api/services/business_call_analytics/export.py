"""CSV and JSON export for business call analytics."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from api.services.business_call_analytics.schema import EXPORT_COLUMNS, kpi_label
from api.services.business_call_analytics.types import (
    BusinessCallMetricsSnapshot,
    BusinessCallReport,
)


def _ts_label(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def export_metrics_csv(snapshot: BusinessCallMetricsSnapshot) -> tuple[io.StringIO, str]:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(list(EXPORT_COLUMNS))
    for kpi_id, kpi in snapshot.kpis.items():
        writer.writerow(
            [
                kpi_id,
                kpi_label(kpi_id),
                kpi.value if kpi.value is not None else "",
                kpi.unit,
                kpi.count,
                kpi.success_count,
                kpi.rate if kpi.rate is not None else "",
            ]
        )
    filename = (
        f"business_call_metrics_org{snapshot.organization_id}_"
        f"{_ts_label(snapshot.from_ts)}_{_ts_label(snapshot.to_ts)}.csv"
    )
    output.seek(0)
    return output, filename


def export_report_csv(report: BusinessCallReport) -> tuple[io.StringIO, str]:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["summary", "organization_id", report.organization_id])
    writer.writerow(["summary", "total_calls", report.summary.total_calls])
    for kpi_id, kpi in report.summary.kpis.items():
        writer.writerow(["kpi", kpi_id, kpi.value if kpi.value is not None else ""])
        writer.writerow(["kpi_rate", kpi_id, kpi.rate if kpi.rate is not None else ""])
    for lang, data in report.by_language.items():
        writer.writerow(["language", lang, data.get("total_events", 0)])
        writer.writerow(
            [
                "language_sentiment",
                lang,
                data.get("avg_sentiment", ""),
            ]
        )
    for row in report.by_day:
        writer.writerow(
            [
                "timeseries",
                f"{row.get('metric')}:{row.get('bucket')}",
                row.get("rate", row.get("avg", row.get("count", ""))),
            ]
        )
    for item in report.top_events:
        writer.writerow(
            ["top_event", item.get("event_type"), item.get("count")]
        )
    filename = (
        f"business_call_report_org{report.organization_id}_"
        f"{_ts_label(report.from_ts)}_{_ts_label(report.to_ts)}.csv"
    )
    output.seek(0)
    return output, filename


def export_metrics_json(snapshot: BusinessCallMetricsSnapshot) -> dict[str, Any]:
    return snapshot.to_dict()


def export_report_json(report: BusinessCallReport) -> dict[str, Any]:
    return report.to_dict()
