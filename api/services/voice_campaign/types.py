"""Types for voice campaign management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LocaleConfig:
    """Multilingual campaign defaults."""

    default_locale: str = "mixed"
    fallback_locales: list[str] = field(default_factory=lambda: ["en", "sw"])
    locale_column: str = "preferred_locale"

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_locale": self.default_locale,
            "fallback_locales": list(self.fallback_locales),
            "locale_column": self.locale_column,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> LocaleConfig:
        if not raw:
            return cls()
        return cls(
            default_locale=str(raw.get("default_locale", "mixed")),
            fallback_locales=list(raw.get("fallback_locales") or ["en", "sw"]),
            locale_column=str(raw.get("locale_column", "preferred_locale")),
        )


@dataclass
class CampaignQueueStats:
    campaign_id: int
    queued: int = 0
    processing: int = 0
    processed: int = 0
    failed: int = 0
    scheduled_retries: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "queued": self.queued,
            "processing": self.processing,
            "processed": self.processed,
            "failed": self.failed,
            "scheduled_retries": self.scheduled_retries,
            "total": self.total,
        }


@dataclass
class CampaignAnalyticsSnapshot:
    campaign_id: int
    organization_id: int
    state: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    queue: CampaignQueueStats
    answer_rate: float | None = None
    retry_rate: float | None = None
    avg_call_duration_s: float | None = None
    outcomes: dict[str, int] = field(default_factory=dict)
    locales: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "organization_id": self.organization_id,
            "state": self.state,
            "total_rows": self.total_rows,
            "processed_rows": self.processed_rows,
            "failed_rows": self.failed_rows,
            "queue": self.queue.to_dict(),
            "answer_rate": self.answer_rate,
            "retry_rate": self.retry_rate,
            "avg_call_duration_s": self.avg_call_duration_s,
            "outcomes": dict(self.outcomes),
            "locales": dict(self.locales),
        }
