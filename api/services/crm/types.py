"""CRM domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CustomerProfile:
    """Aggregated customer view for agents and workflows."""

    id: int
    customer_uuid: str
    organization_id: int
    phone_e164: str
    full_name: str
    email: str | None
    preferred_locale: str
    secondary_locales: list[str]
    external_crm_id: str | None
    is_active: bool
    total_outstanding: float
    debt_accounts: list[dict[str, Any]]
    payment_history: list[dict[str, Any]]
    call_history: list[dict[str, Any]]
    escalation_history: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "customer_uuid": self.customer_uuid,
            "organization_id": self.organization_id,
            "phone_e164": self.phone_e164,
            "full_name": self.full_name,
            "email": self.email,
            "preferred_locale": self.preferred_locale,
            "secondary_locales": self.secondary_locales,
            "external_crm_id": self.external_crm_id,
            "is_active": self.is_active,
            "total_outstanding": self.total_outstanding,
            "debt_accounts": self.debt_accounts,
            "payment_history": self.payment_history,
            "call_history": self.call_history,
            "escalation_history": self.escalation_history,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
