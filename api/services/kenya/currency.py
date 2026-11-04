"""Parse conversational Kenyan shilling amounts into numeric KES."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from api.services.kenya.config import KENYA, KenyaMarketConfig
from api.services.kenya.formatters import format_kes

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}
_SWAHILI = {"mia": 100, "elfu": 1000, "laki": 100_000}

_CURRENCY_WORDS = re.compile(
    r"\b(ksh|kes|shillings?|shilingi|bob|mboch|money|pesa)\b",
    re.I,
)
_K_SUFFIX = re.compile(r"^(\d+(?:\.\d+)?)\s*k$", re.I)
_NUMERIC = re.compile(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class ParsedKesAmount:
    original: str
    amount: Decimal | None
    valid: bool
    requires_confirmation: bool
    formatted: str | None
    error: str | None

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "amount": str(self.amount) if self.amount is not None else None,
            "valid": self.valid,
            "requires_confirmation": self.requires_confirmation,
            "formatted": self.formatted,
            "error": self.error,
        }


def parse_kes(
    raw: str | None,
    *,
    config: KenyaMarketConfig = KENYA,
) -> ParsedKesAmount:
    original = "" if raw is None else str(raw).strip()
    if not original:
        return ParsedKesAmount(original, None, False, True, None, "empty")

    cleaned = _CURRENCY_WORDS.sub(" ", original.lower())
    cleaned = cleaned.replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    amount = _parse_k_suffix(cleaned)
    if amount is None:
        amount = _parse_numeric(cleaned)
    if amount is None:
        amount = _parse_words(cleaned)

    if amount is None:
        return ParsedKesAmount(original, None, False, True, None, "unparsed")
    if amount <= 0:
        return ParsedKesAmount(original, amount, False, True, None, "non_positive")

    quantized = amount.quantize(Decimal("0.01"))
    return ParsedKesAmount(
        original=original,
        amount=quantized,
        valid=True,
        requires_confirmation=True,
        formatted=format_kes(quantized, config=config),
        error=None,
    )


def confirm_kes(parsed: ParsedKesAmount, confirmed_amount: Decimal | float | int) -> bool:
    if not parsed.valid or parsed.amount is None:
        return False
    return parsed.amount == Decimal(str(confirmed_amount)).quantize(Decimal("0.01"))


def _parse_k_suffix(text: str) -> Decimal | None:
    match = _K_SUFFIX.match(text.replace(" ", ""))
    if not match:
        compact = text.replace(" ", "")
        match = _K_SUFFIX.match(compact)
    if not match:
        return None
    return Decimal(match.group(1)) * Decimal(1000)


def _parse_numeric(text: str) -> Decimal | None:
    candidate = text.replace(" ", "")
    if not _NUMERIC.match(candidate):
        return None
    try:
        return Decimal(candidate.replace(",", ""))
    except InvalidOperation:
        return None


def _parse_words(text: str) -> Decimal | None:
    tokens = [t for t in re.split(r"[^a-z]+", text.lower()) if t]
    if not tokens:
        return None
    total = Decimal(0)
    current = Decimal(0)
    used = False
    for token in tokens:
        if token in _UNITS:
            current += _UNITS[token]
            used = True
        elif token in _SCALES or token in _SWAHILI:
            scale = Decimal(_SCALES.get(token) or _SWAHILI[token])
            current = (current or Decimal(1)) * scale
            if scale >= 1000:
                total += current
                current = Decimal(0)
            used = True
        elif token in {"and", "na"}:
            continue
        else:
            return None
    if not used:
        return None
    return total + current
