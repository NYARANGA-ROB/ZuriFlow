from __future__ import annotations

from api.services.whatsapp.config import WhatsAppOrgConfig
from api.services.whatsapp.providers.base import WhatsAppProvider
from api.services.whatsapp.providers.meta import MetaWhatsAppProvider
from api.services.whatsapp.providers.twilio import TwilioWhatsAppProvider
from api.services.whatsapp.types import WhatsAppProviderName


def get_whatsapp_provider(
    provider_name: str,
    config: WhatsAppOrgConfig,
) -> WhatsAppProvider:
    name = provider_name.lower()
    if name == WhatsAppProviderName.META.value:
        if not config.meta or not config.meta.access_token:
            raise ValueError("Meta WhatsApp is not configured for this organization")
        return MetaWhatsAppProvider(config.meta)
    if name == WhatsAppProviderName.TWILIO.value:
        if not config.twilio or not config.twilio.account_sid:
            raise ValueError("Twilio WhatsApp is not configured for this organization")
        return TwilioWhatsAppProvider(config.twilio)
    raise ValueError(f"Unsupported WhatsApp provider: {provider_name}")
