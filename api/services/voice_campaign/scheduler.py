"""Campaign scheduler — timezone-aware dial windows and deferred start."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger


class CampaignScheduler:
    """Evaluate whether a campaign or contact may be dialed now."""

    @staticmethod
    def is_campaign_started(campaign) -> bool:
        meta = campaign.orchestrator_metadata or {}
        scheduled_start = meta.get("scheduled_start_at")
        if not scheduled_start:
            return True
        try:
            start_dt = datetime.fromisoformat(str(scheduled_start).replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            return datetime.now(UTC) >= start_dt
        except ValueError:
            logger.warning("invalid scheduled_start_at on campaign {}", campaign.id)
            return True

    @staticmethod
    def is_within_campaign_schedule(campaign, *, now: datetime | None = None) -> bool:
        """Campaign-level weekly schedule in orchestrator_metadata.schedule_config."""
        meta = campaign.orchestrator_metadata or {}
        schedule_config = meta.get("schedule_config")
        if not schedule_config:
            return True
        if not schedule_config.get("enabled", False):
            return True
        slots = schedule_config.get("slots") or []
        if not slots:
            return True

        timezone_str = schedule_config.get("timezone", "UTC")
        try:
            tz = ZoneInfo(timezone_str)
        except (KeyError, Exception):
            return True

        local_now = (now or datetime.now(UTC)).astimezone(tz)
        current_day = local_now.weekday()
        current_time = local_now.strftime("%H:%M")

        for slot in slots:
            if slot.get("day_of_week") == current_day:
                start = slot.get("start_time", "")
                end = slot.get("end_time", "")
                if start <= current_time < end:
                    return True
        return False

    @staticmethod
    def is_contact_callable(
        context_variables: dict[str, Any],
        *,
        campaign,
        contact_timezone_field: str = "timezone",
        now: datetime | None = None,
    ) -> bool:
        """Per-contact timezone window using context_variables or campaign schedule."""
        contact_tz = context_variables.get(contact_timezone_field)
        if not contact_tz:
            return CampaignScheduler.is_within_campaign_schedule(campaign, now=now)

        meta = campaign.orchestrator_metadata or {}
        schedule_config = meta.get("schedule_config") or {}
        slots = schedule_config.get("slots") or [
            {"day_of_week": d, "start_time": "09:00", "end_time": "18:00"} for d in range(5)
        ]

        try:
            tz = ZoneInfo(str(contact_tz))
        except (KeyError, Exception):
            return CampaignScheduler.is_within_campaign_schedule(campaign, now=now)

        local_now = (now or datetime.now(UTC)).astimezone(tz)
        current_day = local_now.weekday()
        current_time = local_now.strftime("%H:%M")
        for slot in slots:
            if slot.get("day_of_week") == current_day:
                start = slot.get("start_time", "09:00")
                end = slot.get("end_time", "18:00")
                if start <= current_time < end:
                    return True
        return False

    @staticmethod
    def resolve_locale(
        context_variables: dict[str, Any],
        *,
        default_locale: str = "mixed",
        locale_column: str = "preferred_locale",
    ) -> str:
        for key in (locale_column, "locale", "language", "preferred_locale"):
            value = context_variables.get(key)
            if value:
                return str(value)
        return default_locale

    def can_schedule_batch(self, campaign, *, now: datetime | None = None) -> bool:
        if not self.is_campaign_started(campaign):
            return False
        return self.is_within_campaign_schedule(campaign, now=now)
