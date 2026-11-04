from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

from api.constants import (
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_LOCKOUT_THRESHOLD,
    LOGIN_RATE_LIMIT_MAX,
    LOGIN_RATE_LIMIT_WINDOW_S,
)

_failures: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}
_rate: dict[str, list[float]] = defaultdict(list)


def _prune(bucket: list[float], window_s: float, now: float) -> list[float]:
    cutoff = now - window_s
    return [ts for ts in bucket if ts >= cutoff]


def assert_login_allowed(identity: str) -> None:
    now = time.monotonic()
    locked_until = _lockouts.get(identity, 0)
    if locked_until > now:
        raise HTTPException(status_code=429, detail="Account temporarily locked. Try again later.")
    recent = _prune(_rate[identity], LOGIN_RATE_LIMIT_WINDOW_S, now)
    _rate[identity] = recent
    if len(recent) >= LOGIN_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    recent.append(now)
    _rate[identity] = recent


def record_login_failure(identity: str) -> None:
    now = time.monotonic()
    recent = _prune(_failures[identity], LOGIN_LOCKOUT_SECONDS, now)
    recent.append(now)
    _failures[identity] = recent
    if len(recent) >= LOGIN_LOCKOUT_THRESHOLD:
        _lockouts[identity] = now + LOGIN_LOCKOUT_SECONDS


def record_login_success(identity: str) -> None:
    _failures.pop(identity, None)
    _lockouts.pop(identity, None)
    _rate.pop(identity, None)


def reset_login_protection_state() -> None:
    _failures.clear()
    _lockouts.clear()
    _rate.clear()
