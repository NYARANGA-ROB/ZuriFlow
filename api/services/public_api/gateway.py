"""API gateway metadata and route registry."""

from __future__ import annotations

from api.constants import APP_NAME, PUBLIC_API_ENABLED
from api.services.public_api.types import GatewayRouteInfo

API_VERSION = "v1"
GATEWAY_PREFIX = "/api/v1/platform"

_PLATFORM_ROUTES: list[GatewayRouteInfo] = [
    GatewayRouteInfo("GET", "/platform", "Gateway status and API version"),
    GatewayRouteInfo("GET", "/platform/docs", "OpenAPI-style developer documentation"),
    GatewayRouteInfo("GET", "/platform/routes", "Discover supported platform endpoints"),
    GatewayRouteInfo("GET", "/platform/usage", "API usage analytics for your organization"),
    GatewayRouteInfo("GET", "/platform/webhooks", "List webhook subscriptions"),
    GatewayRouteInfo("POST", "/platform/webhooks", "Create a webhook subscription"),
    GatewayRouteInfo("PATCH", "/platform/webhooks/{subscription_uuid}", "Update a webhook"),
    GatewayRouteInfo("DELETE", "/platform/webhooks/{subscription_uuid}", "Delete a webhook"),
    GatewayRouteInfo("POST", "/platform/webhooks/{subscription_uuid}/test", "Send test event"),
    GatewayRouteInfo(
        "POST",
        "/platform/calls/trigger/{trigger_path}",
        "Trigger an outbound voice call via API Trigger node",
    ),
    GatewayRouteInfo(
        "POST",
        "/platform/calls/workflow/{workflow_uuid}",
        "Trigger an outbound voice call by workflow UUID",
    ),
]

_PUBLIC_AGENT_ROUTES: list[GatewayRouteInfo] = [
    GatewayRouteInfo("POST", "/public/agent/{trigger_path}", "Trigger call (published agent)"),
    GatewayRouteInfo("POST", "/public/agent/workflow/{workflow_uuid}", "Trigger call by workflow UUID"),
]


class ApiGateway:
    """Central registry for the Dograh public API platform."""

    def info(self) -> dict:
        return {
            "name": f"{APP_NAME} Public API",
            "version": API_VERSION,
            "enabled": PUBLIC_API_ENABLED,
            "authentication": {
                "type": "api_key",
                "header": "X-API-Key",
                "prefix": "dgr_",
            },
            "rate_limiting": {
                "scope": ["organization", "api_key"],
                "headers": ["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
            },
            "webhooks": {
                "signature_header": "X-Dograh-Signature",
                "timestamp_header": "X-Dograh-Timestamp",
                "algorithm": "HMAC-SHA256",
            },
            "sdk": {
                "python": "dograh_sdk.platform.PlatformClient",
                "typescript": "@dograh/sdk/platform",
            },
        }

    def routes(self) -> list[dict]:
        combined = _PLATFORM_ROUTES + _PUBLIC_AGENT_ROUTES
        return [
            {
                "method": route.method,
                "path": f"/api/v1{route.path}",
                "description": route.description,
                "auth": route.auth,
            }
            for route in combined
        ]


def get_api_gateway() -> ApiGateway:
    return ApiGateway()
