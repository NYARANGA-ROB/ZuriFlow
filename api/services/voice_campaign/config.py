"""Voice campaign management configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from api.services.voice_campaign.types import LocaleConfig


@dataclass
class ThrottleConfig:
    rate_limit_per_second: int = 1
    max_concurrency: int = 2
    batch_size: int = 10
    use_priority_queue: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rate_limit_per_second": self.rate_limit_per_second,
            "max_concurrency": self.max_concurrency,
            "batch_size": self.batch_size,
            "use_priority_queue": self.use_priority_queue,
        }

    @classmethod
    def from_campaign(cls, campaign) -> ThrottleConfig:
        meta = campaign.orchestrator_metadata or {}
        throttle = meta.get("throttle") or {}
        return cls(
            rate_limit_per_second=int(campaign.rate_limit_per_second or 1),
            max_concurrency=int(meta.get("max_concurrency", 2)),
            batch_size=int(throttle.get("batch_size", 10)),
            use_priority_queue=bool(throttle.get("use_priority_queue", True)),
        )


@dataclass
class VoiceCampaignConfig:
    enabled: bool = True
    locale: LocaleConfig = field(default_factory=LocaleConfig)
    throttle: ThrottleConfig = field(default_factory=ThrottleConfig)
    scheduled_start_at: str | None = None
    contact_timezone_field: str = "timezone"

    @classmethod
    def from_campaign(cls, campaign) -> VoiceCampaignConfig:
        meta = campaign.orchestrator_metadata or {}
        locale_raw = meta.get("locale_config")
        return cls(
            enabled=bool(meta.get("voice_campaign_enabled", True)),
            locale=LocaleConfig.from_dict(locale_raw),
            throttle=ThrottleConfig.from_campaign(campaign),
            scheduled_start_at=meta.get("scheduled_start_at"),
            contact_timezone_field=str(meta.get("contact_timezone_field", "timezone")),
        )

    def to_metadata_patch(self) -> dict[str, Any]:
        return {
            "voice_campaign_enabled": self.enabled,
            "locale_config": self.locale.to_dict(),
            "throttle": self.throttle.to_dict(),
            "scheduled_start_at": self.scheduled_start_at,
            "contact_timezone_field": self.contact_timezone_field,
        }
