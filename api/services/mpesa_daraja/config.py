from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.constants import MPESA_ENABLED, MPESA_ENVIRONMENT
from api.enums import OrganizationConfigurationKey
from api.services.mpesa_daraja.types import MpesaEnvironment


@dataclass(frozen=True)
class MpesaDarajaConfig:
    enabled: bool
    environment: MpesaEnvironment
    consumer_key: str
    consumer_secret: str
    shortcode: str
    passkey: str
    callback_base_url: str
    webhook_secret: str | None = None
    transaction_type: str = "CustomerPayBillOnline"
    initiator_name: str | None = None
    security_credential: str | None = None

    @property
    def base_url(self) -> str:
        if self.environment == MpesaEnvironment.PRODUCTION:
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @property
    def stk_callback_url(self) -> str:
        return f"{self.callback_base_url.rstrip('/')}/stk"

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> MpesaDarajaConfig:
        if not raw:
            env = MpesaEnvironment(MPESA_ENVIRONMENT)
            return cls(
                enabled=MPESA_ENABLED,
                environment=env,
                consumer_key="",
                consumer_secret="",
                shortcode="",
                passkey="",
                callback_base_url="",
            )

        env_raw = raw.get("environment", MPESA_ENVIRONMENT)
        try:
            env = MpesaEnvironment(str(env_raw).lower())
        except ValueError:
            env = MpesaEnvironment.SANDBOX

        return cls(
            enabled=bool(raw.get("enabled", MPESA_ENABLED)),
            environment=env,
            consumer_key=str(raw.get("consumer_key", "")),
            consumer_secret=str(raw.get("consumer_secret", "")),
            shortcode=str(raw.get("shortcode", "")),
            passkey=str(raw.get("passkey", "")),
            callback_base_url=str(raw.get("callback_base_url", "")),
            webhook_secret=raw.get("webhook_secret"),
            transaction_type=str(
                raw.get("stk_push_transaction_type", "CustomerPayBillOnline")
            ),
            initiator_name=raw.get("initiator_name"),
            security_credential=raw.get("security_credential"),
        )

    def validate_for_stk(self) -> str | None:
        if not self.enabled:
            return "M-Pesa is disabled"
        if not self.consumer_key or not self.consumer_secret:
            return "Missing Daraja consumer credentials"
        if not self.shortcode or not self.passkey:
            return "Missing shortcode or passkey"
        if not self.callback_base_url:
            return "Missing callback_base_url"
        return None


ORG_CONFIG_KEY = OrganizationConfigurationKey.MPESA_DARAJA_CONFIGURATION.value
