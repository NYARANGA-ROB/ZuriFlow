"""Tests for M-Pesa Daraja integration."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest

from api.services.mpesa_daraja.client import _mpesa_phone, _password, _timestamp
from api.services.mpesa_daraja.config import MpesaDarajaConfig
from api.services.mpesa_daraja.types import MpesaEnvironment
from api.services.mpesa_daraja.webhook import parse_stk_callback, verify_hmac_signature


def test_mpesa_phone_normalization():
    assert _mpesa_phone("+254712345678") == "254712345678"
    assert _mpesa_phone("0712345678") == "254712345678"


def test_password_generation():
    ts = "20260101120000"
    pwd = _password("174379", "passkey", ts)
    assert isinstance(pwd, str)
    assert len(pwd) > 0


def test_parse_stk_callback_success():
    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "m-1",
                "CheckoutRequestID": "co-1",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 100},
                        {"Name": "MpesaReceiptNumber", "Value": "QAB123"},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                    ]
                },
            }
        }
    }
    result = parse_stk_callback(payload)
    assert result.is_success is True
    assert result.checkout_request_id == "co-1"
    assert result.mpesa_receipt_number == "QAB123"
    assert result.amount == 100.0


def test_parse_stk_callback_cancelled():
    payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "co-2",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user",
            }
        }
    }
    result = parse_stk_callback(payload)
    assert result.is_success is False
    assert result.result_code == 1032


def test_webhook_hmac_validation():
    body = json.dumps({"test": True}).encode()
    secret = "webhook-secret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_hmac_signature(body, secret, f"sha256={sig}") is True
    assert verify_hmac_signature(body, secret, "invalid") is False


def test_config_validate_for_stk():
    config = MpesaDarajaConfig(
        enabled=True,
        environment=MpesaEnvironment.SANDBOX,
        consumer_key="key",
        consumer_secret="secret",
        shortcode="174379",
        passkey="pass",
        callback_base_url="https://api.example.com/mpesa/callbacks",
    )
    assert config.validate_for_stk() is None
    assert config.base_url == "https://sandbox.safaricom.co.ke"


@pytest.mark.asyncio
async def test_callback_processor_idempotent():
    from types import SimpleNamespace

    from api.services.mpesa_daraja.callbacks import MpesaCallbackProcessor

    processor = MpesaCallbackProcessor()
    payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "co-99",
                "ResultCode": 0,
                "ResultDesc": "OK",
                "CallbackMetadata": {
                    "Item": [{"Name": "MpesaReceiptNumber", "Value": "RCP1"}]
                },
            }
        }
    }
    tx = SimpleNamespace(
        id=5,
        status="completed",
        mpesa_receipt_number="RCP1",
        workflow_run_id=None,
    )

    with (
        patch(
            "api.services.mpesa_daraja.callbacks.db_client.get_transaction_by_checkout_request_id",
            AsyncMock(return_value=tx),
        ),
        patch(
            "api.services.mpesa_daraja.callbacks.db_client.append_event",
            AsyncMock(),
        ),
    ):
        result = await processor.process_stk_callback(
            organization_id=1,
            payload=payload,
        )

    assert result["idempotent"] is True
