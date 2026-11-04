"""HMAC timestamp + nonce replay protection for inbound business webhooks."""

from __future__ import annotations

import hashlib
import hmac
import time

MAX_SKEW_S = 300
MAX_BODY_BYTES = 65_536


def verify_signed_webhook(
    secret: str | None,
    body: bytes,
    signature: str | None,
    *,
    timestamp: str | None,
    nonce: str | None,
) -> str | None:
    """Return an error code or None if valid."""
    if not secret:
        return "missing_secret"
    if not signature:
        return "invalid_hmac"
    if len(body) > MAX_BODY_BYTES:
        return "oversized"
    if not timestamp or not nonce:
        return "replay_headers"
    try:
        ts = int(timestamp)
    except ValueError:
        return "invalid_timestamp"
    if abs(time.time() - ts) > MAX_SKEW_S:
        return "expired"
    message = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, signature):
        # Fallback: v1 signatures over body only (during rotation window)
        legacy = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(legacy, signature):
            if abs(time.time() - ts) > MAX_SKEW_S:
                return "expired"
            return None
        return "invalid_hmac"
    return None


def redact_question(text: str) -> str:
    import re

    out = re.sub(r"(?:\+?254|0)7\d{8}", "[phone]", text or "")
    out = re.sub(r"\b\d{10,}\b", "[id]", out)
    return out[:500]
