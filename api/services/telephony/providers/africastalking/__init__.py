"""Africa's Talking telephony provider package."""

from typing import Any, Dict

from api.services.telephony.registry import (
    ProviderSpec,
    ProviderUIField,
    ProviderUIMetadata,
    register,
)

from .config import (
    AfricasTalkingConfigurationRequest,
    AfricasTalkingConfigurationResponse,
)
from .provider import AfricasTalkingProvider
from .transport import create_transport


def _config_loader(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "africastalking",
        "username": value.get("username"),
        "api_key": value.get("api_key"),
        "from_numbers": value.get("from_numbers", []),
    }


_UI_METADATA = ProviderUIMetadata(
    display_name="Africa's Talking",
    docs_url="https://docs.dograh.com/integrations/telephony/africastalking",
    fields=[
        ProviderUIField(
            name="username",
            label="Username",
            type="text",
            sensitive=True,
            description="Your Africa's Talking application username (sandbox or production)",
        ),
        ProviderUIField(
            name="api_key",
            label="API Key",
            type="password",
            sensitive=True,
        ),
        ProviderUIField(
            name="from_numbers",
            label="Phone Numbers",
            type="string-array",
            description=(
                "E.164 numbers on your AT account. Configure the voice callback URL "
                "in the Africa's Talking console to point at Dograh's inbound dispatcher."
            ),
        ),
    ],
)


SPEC = ProviderSpec(
    name="africastalking",
    provider_cls=AfricasTalkingProvider,
    config_loader=_config_loader,
    transport_factory=create_transport,
    transport_sample_rate=8000,
    config_request_cls=AfricasTalkingConfigurationRequest,
    ui_metadata=_UI_METADATA,
    config_response_cls=AfricasTalkingConfigurationResponse,
    account_id_credential_field="username",
)


register(SPEC)


__all__ = [
    "SPEC",
    "AfricasTalkingConfigurationRequest",
    "AfricasTalkingConfigurationResponse",
    "AfricasTalkingProvider",
    "create_transport",
]
