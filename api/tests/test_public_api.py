"""Tests for the public API platform."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from api.constants import APP_NAME
from api.services.public_api.gateway import get_api_gateway
from api.services.public_api.types import WebhookEventType
from api.services.public_api.webhook_manager import (
    sign_webhook_payload,
    verify_webhook_signature,
)


class TestApiGateway:
    def test_gateway_info(self):
        info = get_api_gateway().info()
        assert info["name"] == f"{APP_NAME} Public API"
        assert info["authentication"]["header"] == "X-API-Key"
        assert info["enabled"] is True

    def test_gateway_routes_include_platform_and_public_agent(self):
        routes = get_api_gateway().routes()
        paths = {route["path"] for route in routes}
        assert "/api/v1/platform" in paths
        assert any("/public/agent/" in path for path in paths)


class TestWebhookSigning:
    def test_sign_and_verify_roundtrip(self):
        secret = "test-secret"
        timestamp = "1719216000"
        body = json.dumps({"type": "workflow.run.completed"}, sort_keys=True)
        signature = sign_webhook_payload(secret, timestamp, body)
        assert signature.startswith("sha256=")
        assert verify_webhook_signature(secret, timestamp, body, signature)

    def test_verify_rejects_tampered_body(self):
        secret = "test-secret"
        timestamp = "1719216000"
        body = '{"type":"workflow.run.completed"}'
        signature = sign_webhook_payload(secret, timestamp, body)
        assert not verify_webhook_signature(secret, timestamp, '{"type":"tampered"}', signature)


class TestWebhookEventTypes:
    def test_event_values_are_stable(self):
        assert WebhookEventType.WORKFLOW_RUN_COMPLETED.value == "workflow.run.completed"
        assert WebhookEventType.CALL_INITIATED.value == "call.initiated"


class TestPlatformSdk:
    def test_platform_client_import(self):
        from dograh_sdk import PlatformClient

        client = PlatformClient(api_key="dgr_test")
        assert client._http.headers["X-API-Key"] == "dgr_test"
        client.close()

    def test_manual_hmac_matches_manager_helper(self):
        secret = "abc"
        timestamp = "100"
        body = '{"a":1}'
        expected = hmac.new(
            secret.encode(),
            f"{timestamp}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()
        assert sign_webhook_payload(secret, timestamp, body) == f"sha256={expected}"
