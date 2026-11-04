"""Kenyan number, date, and currency display formatting."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from api.services.kenya.config import KENYA, KenyaMarketConfig


def format_kes(
    amount: Decimal | float | int,
    *,
    config: KenyaMarketConfig = KENYA,
    with_code: bool = True,
) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    negative = value < 0
    value = abs(value)
    whole, frac = f"{value:.2f}".split(".")
    grouped = _group_thousands(whole, config.thousands_separator)
    formatted = f"{grouped}{config.decimal_separator}{frac}"
    if negative:
        formatted = f"-{formatted}"
    if with_code:
        return f"{config.currency_code} {formatted}"
    return f"{config.currency_symbol} {formatted}"


def format_kenya_date(value: date | datetime, *, config: KenyaMarketConfig = KENYA) -> str:
    if isinstance(value, datetime):
        value = value.astimezone(ZoneInfo(config.timezone)).date()
    return value.strftime(config.date_format)


def format_kenya_time(value: time | datetime, *, config: KenyaMarketConfig = KENYA) -> str:
    if isinstance(value, datetime):
        value = value.astimezone(ZoneInfo(config.timezone)).time()
    return value.strftime(config.time_format)


def format_kenya_datetime(value: datetime, *, config: KenyaMarketConfig = KENYA) -> str:
    local = value.astimezone(ZoneInfo(config.timezone))
    return local.strftime(config.datetime_format)


def _group_thousands(digits: str, sep: str) -> str:
    parts: list[str] = []
    while digits:
        parts.append(digits[-3:])
        digits = digits[:-3]
    return sep.join(reversed(parts))
