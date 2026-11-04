"""Reusable KenyaContext for workflows, tools, and pipelines."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from api.services.kenya.config import (
    KENYA,
    KenyaLanguage,
    KenyaMarketConfig,
    SUPPORTED_LANGUAGE_VALUES,
)
from api.services.kenya.hours import is_within_business_hours
from api.services.kenya.styles import get_style


@dataclass(frozen=True)
class KenyaContext:
    locale: str
    timezone: str
    language: str
    currency: str
    phone_country: str
    country_name: str
    iso_country_code: str
    date_format: str
    time_format: str
    business_hours: tuple
    is_business_hours: bool
    conversation_style: str = "customer_care"
    localization: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["business_hours"] = [
            {
                "weekday": w.weekday,
                "start": f"{w.start_hour:02d}:{w.start_minute:02d}",
                "end": f"{w.end_hour:02d}:{w.end_minute:02d}",
                "enabled": w.enabled,
            }
            for w in self.business_hours
        ]
        return data


KENYA_CONTEXT_KEY = "kenya_context"


def build_kenya_context(
    *,
    language: str | KenyaLanguage | None = None,
    timezone: str | None = None,
    conversation_style: str | None = None,
    config: KenyaMarketConfig = KENYA,
) -> KenyaContext:
    lang = _coerce_language(language) if language is not None else config.default_language
    tz = timezone or config.timezone
    style = get_style(conversation_style)
    loc = {
        "supported_languages": list(SUPPORTED_LANGUAGE_VALUES),
        "currency_symbol": config.currency_symbol,
        "thousands_separator": config.thousands_separator,
        "decimal_separator": config.decimal_separator,
        "calling_code": config.calling_code,
        "prompt_overlay": style.prompt_overlay,
        "follow_caller_language": style.follow_caller_language,
    }
    return KenyaContext(
        locale=config.locale,
        timezone=tz,
        language=lang.value,
        currency=config.currency_code,
        phone_country=config.iso_country_code,
        country_name=config.country_name,
        iso_country_code=config.iso_country_code,
        date_format=config.date_format,
        time_format=config.time_format,
        business_hours=config.business_hours,
        is_business_hours=is_within_business_hours(),
        conversation_style=style.style.value,
        localization=loc,
    )


def attach_kenya_context(
    call_context: dict[str, Any] | None,
    *,
    language: str | None = None,
    timezone: str | None = None,
) -> dict[str, Any]:
    """Merge KenyaContext into workflow call_context_vars without clobbering keys."""
    merged = dict(call_context or {})
    if KENYA_CONTEXT_KEY not in merged:
        merged[KENYA_CONTEXT_KEY] = build_kenya_context(
            language=language or merged.get("preferred_locale"),
            timezone=timezone or merged.get("timezone"),
            conversation_style=merged.get("kenya_conversation_style")
            or merged.get("conversation_style"),
        ).to_dict()
    # Flat aliases for existing template variables.
    ctx = merged[KENYA_CONTEXT_KEY]
    merged.setdefault("timezone", ctx["timezone"])
    merged.setdefault("currency", ctx["currency"])
    merged.setdefault("locale", ctx["locale"])
    return merged


def _coerce_language(value: str | KenyaLanguage) -> KenyaLanguage:
    if isinstance(value, KenyaLanguage):
        return value
    raw = str(value).lower()
    aliases = {
        "english": KenyaLanguage.ENGLISH,
        "en": KenyaLanguage.ENGLISH,
        "kiswahili": KenyaLanguage.KISWAHILI,
        "swahili": KenyaLanguage.KISWAHILI,
        "sw": KenyaLanguage.KISWAHILI,
        "sheng": KenyaLanguage.SHENG,
        "mixed": KenyaLanguage.MIXED,
    }
    return aliases.get(raw, KenyaLanguage.MIXED)
