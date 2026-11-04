from __future__ import annotations

import hmac
import hashlib
import secrets
import time
from base64 import b32decode, b32encode


def generate_totp_secret() -> str:
    return b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_code(secret: str, *, timestamp: int | None = None, digits: int = 6, period: int = 30) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = b32decode(padded, casefold=True)
    counter = int((timestamp if timestamp is not None else time.time()) // period)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return f"{number % (10 ** digits):0{digits}d}"


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    if not code or not code.isdigit():
        return False
    now = int(time.time())
    expected = {totp_code(secret, timestamp=now + offset * 30) for offset in range(-window, window + 1)}
    return hmac.compare_digest(code.zfill(6), code.zfill(6)) and code.zfill(6) in expected


def provisioning_uri(*, email: str, secret: str, issuer: str = "ZuriFlow") -> str:
    return (
        f"otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    )


def new_recovery_codes(count: int = 8) -> list[str]:
    return [secrets.token_hex(4) for _ in range(count)]
