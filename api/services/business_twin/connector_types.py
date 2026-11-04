"""Connector capabilities and lifecycle. Providers are pluggable; LLM never sees URLs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

DATA_UNAVAILABLE = {
    "code": "DATA_UNAVAILABLE",
    "verified": False,
    "plane": "live",
    "message": "I don't have the latest information on that. Let me connect you with someone who can confirm.",
}

LIFECYCLE = (
    "discovered",
    "connect",
    "authenticate",
    "test",
    "validate",
    "initial_sync",
    "active",
    "monitor",
    "reauthenticate",
    "disconnected",
)

CAPABILITIES: dict[str, tuple[str, ...]] = {
    "crm": ("customer_lookup", "customer_update", "ticket_create", "ticket_lookup"),
    "inventory": ("product_lookup", "inventory_lookup", "price_lookup"),
    "booking": ("availability", "create_booking", "cancel_booking", "reschedule_booking"),
    "order": ("order_lookup", "order_create", "order_update", "delivery_status"),
    "payment": ("payment_status", "transaction_lookup"),
    "website": ("ingest",),
    "document": ("import",),
    "csv": ("import",),
    "rest": (),  # filled from configured endpoints only
    "webhook": ("ingest_event",),
}


@dataclass
class ConnectorHealth:
    connection_status: str
    lifecycle_state: str
    last_successful_request: str | None
    last_successful_sync: str | None
    last_failure: str | None
    latency_ms: int | None
    error_rate: float
    authentication_status: str
    rate_limit_status: str = "ok"
    records_synchronized: int = 0
    healthy: bool = True
    attention: str | None = None


@dataclass
class ConnectorSyncResult:
    ok: bool
    records: int = 0
    error: str | None = None
    latency_ms: int | None = None


@dataclass
class ConnectorCredentials:
    """Never log or return this to the LLM/frontend."""

    payload: dict[str, Any] = field(default_factory=dict)


class BusinessConnector(Protocol):
    adapter_key: str
    provider_kind: str

    def capabilities(self) -> tuple[str, ...]: ...

    async def test_connection(self, organization_id: int) -> ConnectorSyncResult: ...

    async def invoke(
        self, capability: str, arguments: dict[str, Any], *, organization_id: int
    ) -> dict[str, Any]: ...


def capabilities_for(provider_kind: str, configured: list[str] | None = None) -> tuple[str, ...]:
    if provider_kind == "rest":
        return tuple(configured or ())
    return CAPABILITIES.get(provider_kind, ())


def validate_response(payload: dict[str, Any], required: list[str]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    for field_name in required:
        if field_name not in payload or payload[field_name] is None:
            return None
    return payload
