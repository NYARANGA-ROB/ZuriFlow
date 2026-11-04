"""Request/response schemas for the public API platform."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl

from api.services.public_api.types import WebhookEventType


class GatewayInfoResponse(BaseModel):
    name: str
    version: str
    enabled: bool
    authentication: Dict[str, Any]
    rate_limiting: Dict[str, Any]
    webhooks: Dict[str, Any]
    sdk: Dict[str, str]


class GatewayRouteResponse(BaseModel):
    method: str
    path: str
    description: str
    auth: str


class ApiUsageResponse(BaseModel):
    organization_id: int
    api_key_id: Optional[int] = None
    total_requests: int = 0
    error_requests: int = 0
    avg_latency_ms: Optional[float] = None
    top_paths: Dict[str, int] = Field(default_factory=dict)


class CreateWebhookRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    events: List[WebhookEventType] = Field(min_length=1)


class UpdateWebhookRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    is_active: Optional[bool] = None


class WebhookSubscriptionResponse(BaseModel):
    subscription_uuid: str
    name: str
    url: str
    events: List[str]
    is_active: bool
    created_at: Optional[str] = None
    secret: Optional[str] = Field(
        default=None,
        description="Returned only on create; store securely — not shown again.",
    )


class WebhookDeliveryResponse(BaseModel):
    subscription_uuid: str
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    response_body: Optional[str] = None


class PlatformTriggerCallRequest(BaseModel):
    phone_number: str
    initial_context: Optional[dict] = None
    telephony_configuration_id: int | None = None
