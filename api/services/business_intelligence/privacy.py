"""Privacy helpers for analytics: redact PII and drop identifiers."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_PHONE = re.compile(r"(?:\+?254|0)7\d{8}")
_ID = re.compile(r"\b\d{6,10}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact_text(value: str | None, *, max_len: int = 240) -> str | None:
    if not value:
        return None
    text = _PHONE.sub("[phone]", value)
    text = _EMAIL.sub("[email]", text)
    text = _ID.sub("[id]", text)
    text = " ".join(text.split())
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def hash_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def strip_sensitive_metrics(payload: dict[str, Any], *, include_payments: bool) -> dict[str, Any]:
    data = dict(payload)
    kenyan = dict(data.get("kenyan") or {})
    if not include_payments:
        kenyan.pop("kes_processed", None)
        kenyan.pop("successful_amount", None)
        kenyan.pop("abandoned_amount", None)
    data["kenyan"] = kenyan
    return data
