"""Kenya public holidays (fixed-date + Easter) in Africa/Nairobi."""

from __future__ import annotations

from datetime import date, timedelta

# Name keyed by (month, day) for civil holidays that do not move with Easter.
_FIXED: dict[tuple[int, int], str] = {
    (1, 1): "New Year's Day",
    (5, 1): "Labour Day",
    (6, 1): "Madaraka Day",
    (10, 10): "Utamaduni Day",
    (10, 20): "Mashujaa Day",
    (12, 12): "Jamhuri Day",
    (12, 25): "Christmas Day",
    (12, 26): "Boxing Day",
}


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def kenya_holidays_for_year(year: int) -> dict[date, str]:
    holidays: dict[date, str] = {}
    for (month, day), name in _FIXED.items():
        holidays[date(year, month, day)] = name
    easter = _easter_sunday(year)
    holidays[easter - timedelta(days=2)] = "Good Friday"
    holidays[easter + timedelta(days=1)] = "Easter Monday"
    return holidays


def is_kenya_public_holiday(when: date) -> bool:
    return when in kenya_holidays_for_year(when.year)


def holiday_name(when: date) -> str | None:
    return kenya_holidays_for_year(when.year).get(when)
