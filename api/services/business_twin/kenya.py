"""Kenya-aware helpers for the Digital Twin. Industry templates are data, not engine logic."""

from __future__ import annotations

from api.services.control_plane.setup import INDUSTRIES, KENYA_COUNTIES
from api.services.kenya.config import KENYA
from api.services.kenya.phone import normalize_kenyan_phone

KENYA_PUBLIC_HOLIDAYS_2026 = (
    ("2026-01-01", "New Year's Day"),
    ("2026-04-03", "Good Friday"),
    ("2026-04-06", "Easter Monday"),
    ("2026-05-01", "Labour Day"),
    ("2026-06-01", "Madaraka Day"),
    ("2026-10-20", "Mashujaa Day"),
    ("2026-12-12", "Jamhuri Day"),
    ("2026-12-25", "Christmas Day"),
    ("2026-12-26", "Boxing Day"),
)

INDUSTRY_TEMPLATES: dict[str, dict] = {
    key: {
        "industry_id": key,
        "currency": KENYA.currency_code,
        "timezone": KENYA.timezone,
        "languages": ["en", "sw", "sheng", "mixed"],
        "live_data": ["inventory", "booking", "payment"] if key in {"retail", "hospitality", "healthcare"} else ["payment"],
    }
    for key in (
        *INDUSTRIES,
        "sacco",
        "clinic",
        "pharmacy",
        "school",
        "hotel",
        "restaurant",
        "real_estate",
        "ecommerce",
        "automotive",
        "travel",
        "financial_services",
    )
}


def template_for(industry_id: str | None) -> dict:
    if not industry_id:
        return INDUSTRY_TEMPLATES.get("other", next(iter(INDUSTRY_TEMPLATES.values())))
    return INDUSTRY_TEMPLATES.get(industry_id, INDUSTRY_TEMPLATES.get("other", {}))


def normalize_phone(value: str) -> str:
    parsed = normalize_kenyan_phone(value)
    return parsed.e164 if parsed.valid and parsed.e164 else value


def counties() -> list[str]:
    return list(KENYA_COUNTIES)
