from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.constants import MPESA_ENABLED


@dataclass(frozen=True)
class VoiceMpesaConfig:
    enabled: bool = False
    default_amount: float = 100.0
    max_retries: int = 3
    verification_poll_interval_s: float = 3.0
    verification_timeout_s: float = 120.0
    auto_offer_on_payment_intent: bool = True
    send_whatsapp_receipt: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> VoiceMpesaConfig:
        if not raw:
            return cls(enabled=MPESA_ENABLED)
        return cls(
            enabled=bool(raw.get("enabled", MPESA_ENABLED)),
            default_amount=float(raw.get("default_amount", 100.0)),
            max_retries=int(raw.get("max_retries", 3)),
            verification_poll_interval_s=float(raw.get("verification_poll_interval_s", 3.0)),
            verification_timeout_s=float(raw.get("verification_timeout_s", 120.0)),
            auto_offer_on_payment_intent=bool(raw.get("auto_offer_on_payment_intent", True)),
            send_whatsapp_receipt=bool(raw.get("send_whatsapp_receipt", True)),
        )
