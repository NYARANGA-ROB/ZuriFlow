from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.constants import WHATSAPP_DEFAULT_PROVIDER, WHATSAPP_ENABLED
from api.enums import OrganizationConfigurationKey
from api.services.whatsapp.post_call.config import PostCallWorkflowConfig


@dataclass(frozen=True)
class MetaWhatsAppConfig:
    access_token: str
    phone_number_id: str
    app_secret: str | None = None
    verify_token: str | None = None
    api_version: str = "v21.0"


@dataclass(frozen=True)
class TwilioWhatsAppConfig:
    account_sid: str
    auth_token: str
    from_number: str


@dataclass(frozen=True)
class EscalationConfig:
    notify_numbers: tuple[str, ...] = ()
    webhook_url: str | None = None


@dataclass(frozen=True)
class WhatsAppOrgConfig:
    enabled: bool
    default_provider: str
    meta: MetaWhatsAppConfig | None = None
    twilio: TwilioWhatsAppConfig | None = None
    escalation: EscalationConfig = EscalationConfig()
    post_call: PostCallWorkflowConfig = PostCallWorkflowConfig()

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> WhatsAppOrgConfig:
        if not raw:
            return cls(enabled=WHATSAPP_ENABLED, default_provider=WHATSAPP_DEFAULT_PROVIDER)

        meta_cfg = None
        if raw.get("meta"):
            m = raw["meta"]
            meta_cfg = MetaWhatsAppConfig(
                access_token=m.get("access_token", ""),
                phone_number_id=m.get("phone_number_id", ""),
                app_secret=m.get("app_secret"),
                verify_token=m.get("verify_token"),
                api_version=m.get("api_version", "v21.0"),
            )

        twilio_cfg = None
        if raw.get("twilio"):
            t = raw["twilio"]
            twilio_cfg = TwilioWhatsAppConfig(
                account_sid=t.get("account_sid", ""),
                auth_token=t.get("auth_token", ""),
                from_number=t.get("from_number", ""),
            )

        escalation_raw = raw.get("escalation") or {}
        escalation = EscalationConfig(
            notify_numbers=tuple(escalation_raw.get("notify_numbers") or ()),
            webhook_url=escalation_raw.get("webhook_url"),
        )

        post_call = PostCallWorkflowConfig.from_dict(raw.get("post_call"))

        return cls(
            enabled=bool(raw.get("enabled", WHATSAPP_ENABLED)),
            default_provider=raw.get("default_provider", WHATSAPP_DEFAULT_PROVIDER),
            meta=meta_cfg,
            twilio=twilio_cfg,
            escalation=escalation,
            post_call=post_call,
        )


ORG_CONFIG_KEY = OrganizationConfigurationKey.WHATSAPP_CONFIGURATION.value
