"""Kenyan-aware outbound number resolution for the telephony domain."""

from __future__ import annotations

from api.services.kenya.phone import KenyanPhoneResult, normalize_kenyan_phone
from api.services.telephony.domain import PhoneNumber
from api.utils.telephony_address import normalize_telephony_address


def resolve_outbound_number(raw: str | None) -> PhoneNumber:
    """Prefer Kenyan mobile rules, then generic E.164 / SIP normalization."""
    original = "" if raw is None else str(raw).strip()
    if not original:
        raise ValueError("empty_phone_number")

    kenyan: KenyanPhoneResult = normalize_kenyan_phone(original)
    if kenyan.valid and kenyan.e164:
        return PhoneNumber(
            e164=kenyan.e164,
            original=original,
            country="KE",
            operator=kenyan.operator,
        )

    compact = original.translate(str.maketrans("", "", " \t-()"))
    looks_kenyan = compact.startswith(("07", "01", "254", "+254", "00"))
    if looks_kenyan and not kenyan.valid:
        raise ValueError(kenyan.error or "invalid_kenyan_mobile")

    address = normalize_telephony_address(original)
    return PhoneNumber(
        e164=address.canonical,
        original=original,
        country=address.country_code,
        operator=None,
    )
