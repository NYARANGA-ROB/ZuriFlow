"""Unit tests for WhatsApp integration layer."""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.whatsapp.config import (
    MetaWhatsAppConfig,
    TwilioWhatsAppConfig,
    WhatsAppOrgConfig,
)
from api.services.whatsapp.providers.meta import MetaWhatsAppProvider
from api.services.whatsapp.providers.twilio import TwilioWhatsAppProvider
from api.services.whatsapp.templates.engine import WhatsAppTemplateEngine
from api.services.whatsapp.types import WhatsAppTemplateName


def test_template_engine_call_summary():
    engine = WhatsAppTemplateEngine()
    body = engine.render(
        WhatsAppTemplateName.CALL_SUMMARY.value,
        {
            "customer_name": "Jane",
            "summary": "Discussed billing.",
            "intent": "billing",
            "next_steps": "Pay invoice",
        },
    )
    assert "Jane" in body
    assert "Discussed billing." in body
    assert "billing" in body
    assert "Pay invoice" in body


def test_template_engine_payment_link():
    engine = WhatsAppTemplateEngine()
    body = engine.render(
        WhatsAppTemplateName.PAYMENT_LINK.value,
        {
            "customer_name": "John",
            "amount": "KES 500",
            "payment_url": "https://pay.example/abc",
            "reference": "INV-1",
        },
    )
    assert "KES 500" in body
    assert "https://pay.example/abc" in body


def test_meta_parse_inbound_webhook():
    provider = MetaWhatsAppProvider(
        MetaWhatsAppConfig(access_token="token", phone_number_id="123")
    )
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Alex"}}],
                            "messages": [
                                {
                                    "from": "254712345678",
                                    "id": "wamid.abc",
                                    "type": "text",
                                    "text": {"body": "Need a human please"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    messages = provider.parse_inbound_webhook(payload)
    assert len(messages) == 1
    assert messages[0].body == "Need a human please"
    assert messages[0].from_phone == "+254712345678"
    assert messages[0].profile_name == "Alex"


@pytest.mark.asyncio
async def test_meta_verify_webhook_signature():
    secret = "test-secret"
    provider = MetaWhatsAppProvider(
        MetaWhatsAppConfig(
            access_token="token",
            phone_number_id="123",
            app_secret=secret,
        )
    )
    body = b'{"hello":"world"}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert await provider.verify_webhook_signature(
        "https://example.com/webhook",
        body,
        {"x-hub-signature-256": f"sha256={digest}"},
    )


def test_twilio_parse_inbound_webhook():
    provider = TwilioWhatsAppProvider(
        TwilioWhatsAppConfig(
            account_sid="AC123",
            auth_token="token",
            from_number="+15550001111",
        )
    )
    payload = {
        "From": "whatsapp:+254700000000",
        "Body": "Confirm appointment",
        "MessageSid": "SM123",
        "ProfileName": "Sam",
    }
    messages = provider.parse_inbound_webhook(payload)
    assert messages[0].from_phone == "+254700000000"
    assert messages[0].body == "Confirm appointment"


@pytest.mark.asyncio
async def test_messaging_send_call_summary_queues_on_failure():
    from api.services.whatsapp.messaging import WhatsAppMessagingService

    service = WhatsAppMessagingService()
    config = WhatsAppOrgConfig(
        enabled=True,
        default_provider="meta",
        meta=MetaWhatsAppConfig(access_token="tok", phone_number_id="pid"),
    )

    mock_provider = AsyncMock()
    mock_provider.send_text.return_value = MagicMock(
        success=False,
        provider_message_id=None,
        error="rate limited",
        raw_response={},
    )

    with (
        patch.object(service, "load_org_config", AsyncMock(return_value=config)),
        patch(
            "api.services.whatsapp.messaging.get_whatsapp_provider",
            return_value=mock_provider,
        ),
        patch.object(service._store, "get_or_create", AsyncMock()) as get_or_create,
        patch.object(service._store, "record_outbound", AsyncMock()) as record_outbound,
        patch.object(service._store, "update_message_status", AsyncMock()),
        patch.object(service._queue, "enqueue_retry", AsyncMock(return_value=True)) as enqueue_retry,
    ):
        conv = MagicMock(id=10)
        msg = MagicMock(id=20)
        get_or_create.return_value = conv
        record_outbound.return_value = msg

        result = await service.send_call_summary(
            organization_id=1,
            phone_e164="+254712345678",
            customer_name="Jane",
            summary="Test summary",
            intent="support",
            next_steps="Wait for agent",
        )

    assert result["success"] is False
    assert result["conversation_id"] == 10
    enqueue_retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_escalate_on_human_request():
    from api.services.whatsapp.messaging import WhatsAppMessagingService

    assert WhatsAppMessagingService._should_escalate("I need to speak to a human")
    assert not WhatsAppMessagingService._should_escalate("Thanks, all good")
