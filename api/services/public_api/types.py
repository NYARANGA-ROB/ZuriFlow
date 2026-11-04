"""Public API platform types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class WebhookEventType(str, Enum):
    WORKFLOW_RUN_STARTED = "workflow.run.started"
    WORKFLOW_RUN_COMPLETED = "workflow.run.completed"
    WORKFLOW_RUN_FAILED = "workflow.run.failed"
    CALL_INITIATED = "call.initiated"
    CALL_COMPLETED = "call.completed"


@dataclass(frozen=True)
class PublicApiContext:
    """Authenticated API key context for platform and public agent routes."""

    organization_id: int
    api_key_id: int
    api_key_prefix: str
    created_by_user_id: int | None


@dataclass(frozen=True)
class GatewayRouteInfo:
    method: str
    path: str
    description: str
    auth: str = "X-API-Key"


@dataclass(frozen=True)
class UsageBucket:
    total_requests: int = 0
    error_requests: int = 0
    total_latency_ms: float = 0.0
    by_path: dict[str, int] | None = None


@dataclass
class WebhookDeliveryResult:
    subscription_uuid: str
    success: bool
    status_code: int | None = None
    error: str | None = None
    response_body: str | None = None


@dataclass
class WebhookPayload:
    id: str
    type: str
    created_at: str
    organization_id: int
    data: dict[str, Any]
