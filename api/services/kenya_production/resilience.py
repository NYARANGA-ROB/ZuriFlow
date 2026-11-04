from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for external APIs (Daraja, WhatsApp)."""

    name: str
    failure_threshold: int = 5
    recovery_timeout_s: float = 30.0
    _failures: int = 0
    _opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.recovery_timeout_s:
            self._failures = 0
            self._opened_at = None
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    def state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "failures": self._failures,
            "open": self._opened_at is not None,
        }


_daraja_breaker = CircuitBreaker(name="daraja", failure_threshold=8, recovery_timeout_s=45.0)
_whatsapp_breaker = CircuitBreaker(name="whatsapp", failure_threshold=10, recovery_timeout_s=60.0)


def daraja_circuit() -> CircuitBreaker:
    return _daraja_breaker


def whatsapp_circuit() -> CircuitBreaker:
    return _whatsapp_breaker
