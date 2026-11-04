from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PostCallWorkflowConfig:
    enabled: bool = False
    auto_send_summary: bool = True
    auto_send_payment_link: bool = True
    auto_send_booking_link: bool = True
    auto_escalate: bool = True
    default_language: str = "en"
    payment_url_template: str | None = None
    booking_url_template: str | None = None
    escalate_on_intents: tuple[str, ...] = ("request_support",)
    escalate_on_dispositions: tuple[str, ...] = ("failed", "escalate", "handoff")
    escalate_on_low_confidence: bool = True
    confidence_threshold: float = 0.5
    max_workflow_attempts: int = 3

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PostCallWorkflowConfig:
        if not raw:
            return cls()
        return cls(
            enabled=bool(raw.get("enabled", False)),
            auto_send_summary=bool(raw.get("auto_send_summary", True)),
            auto_send_payment_link=bool(raw.get("auto_send_payment_link", True)),
            auto_send_booking_link=bool(raw.get("auto_send_booking_link", True)),
            auto_escalate=bool(raw.get("auto_escalate", True)),
            default_language=raw.get("default_language", "en"),
            payment_url_template=raw.get("payment_url_template"),
            booking_url_template=raw.get("booking_url_template"),
            escalate_on_intents=tuple(raw.get("escalate_on_intents") or ("request_support",)),
            escalate_on_dispositions=tuple(
                raw.get("escalate_on_dispositions") or ("failed", "escalate", "handoff")
            ),
            escalate_on_low_confidence=bool(raw.get("escalate_on_low_confidence", True)),
            confidence_threshold=float(raw.get("confidence_threshold", 0.5)),
            max_workflow_attempts=int(raw.get("max_workflow_attempts", 3)),
        )
