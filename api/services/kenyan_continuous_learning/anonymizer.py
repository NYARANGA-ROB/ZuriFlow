"""PII redaction for Kenyan conversation learning samples."""

from __future__ import annotations

import hashlib
import re

_PHONE_RE = re.compile(
    r"(?:\+?254|0)(?:7|1)\d{8}\b|\+254\d{9,12}\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_MPESA_RECEIPT_RE = re.compile(r"\b[A-Z0-9]{8,12}\b")
_NATIONAL_ID_RE = re.compile(r"\b\d{6,8}\b")


def anonymize_text(text: str) -> str:
    if not text:
        return text
    out = _PHONE_RE.sub("[PHONE]", text)
    out = _EMAIL_RE.sub("[EMAIL]", out)
    out = _MPESA_RECEIPT_RE.sub(_redact_receipt, out)
    out = _NATIONAL_ID_RE.sub("[ID]", out)
    return out.strip()


def anonymize_turns(turns: list[dict]) -> list[dict]:
    return [
        {
            **turn,
            "text": anonymize_text(str(turn.get("text", ""))),
        }
        for turn in turns
    ]


def hash_run_reference(workflow_run_id: int, organization_id: int) -> str:
    payload = f"{organization_id}:{workflow_run_id}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _redact_receipt(match: re.Match[str]) -> str:
    token = match.group(0)
    if token.isdigit():
        return "[ID]"
    if len(token) >= 10 and token.isalnum():
        return "[RECEIPT]"
    return token
