"""Central Kenya market configuration. Import this instead of scattering literals."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Tuple


class KenyaLanguage(str, Enum):
    ENGLISH = "en"
    KISWAHILI = "sw"
    SHENG = "sheng"
    MIXED = "mixed"


@dataclass(frozen=True)
class BusinessHoursWindow:
    """Local-time window for a weekday (0=Monday … 6=Sunday)."""

    weekday: int
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    enabled: bool = True


@dataclass(frozen=True)
class KenyaMarketConfig:
    country_name: str = "Kenya"
    iso_country_code: str = "KE"
    calling_code: str = "254"
    timezone: str = "Africa/Nairobi"
    currency_code: str = "KES"
    currency_symbol: str = "KSh"
    locale: str = "en_KE"
    default_language: KenyaLanguage = KenyaLanguage.MIXED
    supported_languages: Tuple[KenyaLanguage, ...] = (
        KenyaLanguage.ENGLISH,
        KenyaLanguage.KISWAHILI,
        KenyaLanguage.SHENG,
        KenyaLanguage.MIXED,
    )
    phone_national_length: int = 9
    date_format: str = "%d/%m/%Y"
    time_format: str = "%H:%M"
    datetime_format: str = "%d/%m/%Y %H:%M"
    thousands_separator: str = ","
    decimal_separator: str = "."
    # Typical Kenyan office hours (EAT). Campaigns may override.
    business_hours: Tuple[BusinessHoursWindow, ...] = (
        BusinessHoursWindow(0, 8, 0, 17, 0),
        BusinessHoursWindow(1, 8, 0, 17, 0),
        BusinessHoursWindow(2, 8, 0, 17, 0),
        BusinessHoursWindow(3, 8, 0, 17, 0),
        BusinessHoursWindow(4, 8, 0, 17, 0),
        BusinessHoursWindow(5, 0, 0, 0, 0, enabled=False),
        BusinessHoursWindow(6, 0, 0, 0, 0, enabled=False),
    )
    # Probable mobile NDC (first two digits after 254).
    operator_prefixes: dict = field(
        default_factory=lambda: {
            "safaricom": frozenset({"70", "71", "72", "74", "79", "11"}),
            "airtel": frozenset({"73", "75", "78", "10"}),
            "telkom": frozenset({"77"}),
            "equitel": frozenset({"76"}),
        }
    )


KENYA = KenyaMarketConfig()

SUPPORTED_LANGUAGE_VALUES: FrozenSet[str] = frozenset(lang.value for lang in KenyaLanguage)
