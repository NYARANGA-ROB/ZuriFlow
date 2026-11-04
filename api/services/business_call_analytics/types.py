"""Types for AI business call analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KpiValue:
    name: str
    value: float | int | None
    unit: str = ""
    count: int = 0
    success_count: int = 0
    rate: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "count": self.count,
            "success_count": self.success_count,
            "rate": self.rate,
            "metadata": dict(self.metadata),
        }


@dataclass
class BusinessCallMetricsSnapshot:
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    total_calls: int = 0
    kpis: dict[str, KpiValue] = field(default_factory=dict)
    rates: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "from_ts": self.from_ts,
            "to_ts": self.to_ts,
            "generated_at": self.generated_at,
            "total_calls": self.total_calls,
            "kpis": {k: v.to_dict() for k, v in self.kpis.items()},
            "rates": dict(self.rates),
        }


@dataclass
class TimeseriesPoint:
    bucket: str
    metric: str
    count: int = 0
    sum: float = 0.0
    avg: float | None = None
    success_count: int = 0
    rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "metric": self.metric,
            "count": self.count,
            "sum": self.sum,
            "avg": self.avg,
            "success_count": self.success_count,
            "rate": self.rate,
        }


@dataclass
class BusinessCallReport:
    organization_id: int
    from_ts: float
    to_ts: float
    generated_at: float
    summary: BusinessCallMetricsSnapshot
    by_language: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_day: list[dict[str, Any]] = field(default_factory=list)
    top_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "from_ts": self.from_ts,
            "to_ts": self.to_ts,
            "generated_at": self.generated_at,
            "summary": self.summary.to_dict(),
            "by_language": dict(self.by_language),
            "by_day": list(self.by_day),
            "top_events": list(self.top_events),
        }
