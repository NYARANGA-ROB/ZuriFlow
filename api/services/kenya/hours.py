"""Kenyan business-hours checks using KenyaMarketConfig."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from api.services.kenya.config import KENYA, KenyaMarketConfig
from api.services.kenya.holidays import is_kenya_public_holiday


def is_within_business_hours(
    when: datetime | None = None,
    *,
    config: KenyaMarketConfig = KENYA,
    respect_holidays: bool = True,
) -> bool:
    tz = ZoneInfo(config.timezone)
    local = (when or datetime.now(tz)).astimezone(tz)
    if respect_holidays and is_kenya_public_holiday(local.date()):
        return False
    weekday = local.weekday()
    for window in config.business_hours:
        if window.weekday != weekday or not window.enabled:
            continue
        start = local.replace(
            hour=window.start_hour, minute=window.start_minute, second=0, microsecond=0
        )
        end = local.replace(
            hour=window.end_hour, minute=window.end_minute, second=0, microsecond=0
        )
        return start <= local < end
    return False
