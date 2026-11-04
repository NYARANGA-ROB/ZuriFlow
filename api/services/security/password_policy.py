from __future__ import annotations

import re

from api.constants import OSS_PASSWORD_MIN_LENGTH

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


class PasswordPolicyError(ValueError):
    pass


def validate_password_policy(password: str) -> str:
    if len(password) < OSS_PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {OSS_PASSWORD_MIN_LENGTH} characters"
        )
    if not _UPPER.search(password):
        raise PasswordPolicyError("Password must include an uppercase letter")
    if not _LOWER.search(password):
        raise PasswordPolicyError("Password must include a lowercase letter")
    if not _DIGIT.search(password):
        raise PasswordPolicyError("Password must include a digit")
    if not _SPECIAL.search(password):
        raise PasswordPolicyError("Password must include a special character")
    lowered = password.lower()
    if any(weak in lowered for weak in ("password", "qwerty", "123456", "dograh", "zuriflow")):
        raise PasswordPolicyError("Password is too common")
    return password
