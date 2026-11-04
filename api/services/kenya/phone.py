"""Kenyan mobile number normalization to E.164 (+254…)."""

from __future__ import annotations

from dataclasses import dataclass

from api.services.kenya.config import KENYA, KenyaMarketConfig

_STRIP = str.maketrans("", "", " \t\n\r-().")


@dataclass(frozen=True)
class KenyanPhoneResult:
    original: str
    e164: str | None
    national: str | None
    valid: bool
    error: str | None
    operator: str | None

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "e164": self.e164,
            "national": self.national,
            "valid": self.valid,
            "error": self.error,
            "operator": self.operator,
        }


def _invalid(original: str, error: str) -> KenyanPhoneResult:
    return KenyanPhoneResult(
        original=original,
        e164=None,
        national=None,
        valid=False,
        error=error,
        operator=None,
    )


def normalize_kenyan_phone(
    raw: str | None,
    *,
    config: KenyaMarketConfig = KENYA,
) -> KenyanPhoneResult:
    """Normalize common Kenyan mobile formats to E.164.

    Accepted: 07XXXXXXXX, 01XXXXXXXX, 2547XXXXXXXX, 2541XXXXXXXX,
    +2547XXXXXXXX, +2541XXXXXXXX (spaces/dashes allowed).
    """
    original = "" if raw is None else str(raw)
    if not original.strip():
        return _invalid(original, "empty")

    compact = original.strip().translate(_STRIP)
    if compact.startswith("00"):
        compact = "+" + compact[2:]

    digits = compact[1:] if compact.startswith("+") else compact
    if not digits.isdigit():
        return _invalid(original, "non_numeric")

    calling = config.calling_code
    national: str | None = None

    if digits.startswith("0") and len(digits) == 10 and digits[1] in {"7", "1"}:
        national = digits[1:]
    elif digits.startswith(calling) and len(digits) == 12 and digits[3] in {"7", "1"}:
        national = digits[3:]
    elif len(digits) == 9 and digits[0] in {"7", "1"}:
        national = digits
    else:
        return _invalid(original, "invalid_kenyan_mobile")

    if len(national) != config.phone_national_length:
        return _invalid(original, "invalid_length")
    if national[0] not in {"7", "1"}:
        return _invalid(original, "invalid_prefix")

    e164 = f"+{calling}{national}"
    operator = _operator_for(national[:2], config)
    return KenyanPhoneResult(
        original=original,
        e164=e164,
        national=national,
        valid=True,
        error=None,
        operator=operator,
    )


def require_e164(raw: str, *, config: KenyaMarketConfig = KENYA) -> str:
    result = normalize_kenyan_phone(raw, config=config)
    if not result.valid or not result.e164:
        raise ValueError(result.error or "invalid_kenyan_mobile")
    return result.e164


def canonical_storage_key(raw: str) -> str:
    """E.164 if Kenyan-valid, else raise. Used for CRM uniqueness."""
    return require_e164(raw)


def _operator_for(ndc: str, config: KenyaMarketConfig) -> str | None:
    prefixes = config.operator_prefixes
    for name, codes in prefixes.items():
        if ndc in codes:
            return name
    return None
