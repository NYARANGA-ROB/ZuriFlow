"""Kenyan business calendar: EAT, holidays, branch hours, announcements."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from api.services.business_twin.kenya import KENYA_PUBLIC_HOLIDAYS_2026
from api.services.kenya.config import KENYA

EAT = ZoneInfo(KENYA.timezone)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def now_eat(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(EAT)
    if now.tzinfo is None:
        return now.replace(tzinfo=EAT)
    return now.astimezone(EAT)


def is_public_holiday(day: datetime) -> tuple[bool, str | None]:
    key = day.strftime("%Y-%m-%d")
    for date_str, name in KENYA_PUBLIC_HOLIDAYS_2026:
        if date_str == key:
            return True, name
    return False, None


def parse_window(value: str | None) -> tuple[str, str] | None:
    if not value or "-" not in value:
        return None
    start, end = value.split("-", 1)
    return start.strip(), end.strip()


def is_open_at(
    *,
    hours_json: dict,
    day: datetime,
    holidays: list[str] | None = None,
    special_closures: list[str] | None = None,
    announcement_closed: bool = False,
) -> dict:
    local = now_eat(day)
    holiday, holiday_name = is_public_holiday(local)
    if holiday or (holidays and local.strftime("%Y-%m-%d") in holidays):
        return {
            "open": False,
            "reason": holiday_name or "public_holiday",
            "timezone": KENYA.timezone,
            "local_date": local.strftime("%Y-%m-%d"),
        }
    if special_closures and local.strftime("%Y-%m-%d") in special_closures:
        return {"open": False, "reason": "special_closure", "timezone": KENYA.timezone}
    if announcement_closed:
        return {"open": False, "reason": "announcement", "timezone": KENYA.timezone}
    weekday = WEEKDAYS[local.weekday()]
    schedule = hours_json.get("schedule") or {}
    window = None
    if weekday in schedule and isinstance(schedule[weekday], dict):
        row = schedule[weekday]
        if not row.get("enabled", True):
            return {"open": False, "reason": "closed_weekday", "timezone": KENYA.timezone}
        window = (row.get("open_time"), row.get("close_time"))
    elif weekday == "saturday":
        window = parse_window(hours_json.get("saturday"))
    elif weekday == "sunday":
        window = parse_window(hours_json.get("sunday"))
    else:
        window = parse_window(hours_json.get("weekdays") or hours_json.get("weekdays_hours"))
    if not window or not window[0] or not window[1]:
        return {"open": False, "reason": "no_hours", "timezone": KENYA.timezone, "verified": False}
    current = local.strftime("%H:%M")
    opened = window[0] <= current < window[1]
    return {
        "open": opened,
        "open_time": window[0],
        "close_time": window[1],
        "timezone": KENYA.timezone,
        "weekday": weekday,
        "local_date": local.strftime("%Y-%m-%d"),
        "verified": True,
    }


def match_branch(locations: list, query: str):
    q = (query or "").lower()
    if not q:
        return None
    for loc in locations:
        name = loc.name if hasattr(loc, "name") else str(loc.get("name") or "")
        county = loc.county if hasattr(loc, "county") else str(loc.get("county") or "")
        if name and (name.lower() in q or q in name.lower()):
            return loc
        if county and county.lower() in q:
            return loc
    return None
