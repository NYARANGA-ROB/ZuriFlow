"""Configurable commercial plan catalog. Prices are never hard-coded in application logic."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from api.constants import ZURIFLOW_PLAN_CATALOG_JSON
from api.services.tenant_billing.schema import (
    TenantBillingPlanSchema,
    TenantQuotaConfig,
    TenantSubscriptionConfig,
    TenantUsageRates,
)

PLAN_IDS = ("starter", "growth", "business", "enterprise")


@lru_cache(maxsize=1)
def load_plan_catalog() -> list[dict[str, Any]]:
    raw = (ZURIFLOW_PLAN_CATALOG_JSON or "").strip()
    if not raw:
        return [
            {
                "id": plan_id,
                "display_name": plan_id.title(),
                "quotas": {},
                "rates": {},
                "currency": "KES",
                "features": _default_features(plan_id),
            }
            for plan_id in PLAN_IDS
        ]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("ZURIFLOW_PLAN_CATALOG_JSON must be a JSON array")
    return data


def plan_from_catalog(plan_id: str) -> TenantBillingPlanSchema:
    for entry in load_plan_catalog():
        if str(entry.get("id") or "").lower() == plan_id.lower():
            rates = TenantUsageRates.model_validate(entry.get("rates") or {})
            quotas = TenantQuotaConfig.model_validate(entry.get("quotas") or {})
            return TenantBillingPlanSchema(
                plan_id=plan_id.lower(),
                currency=str(entry.get("currency") or "KES"),
                rates=rates,
                quotas=quotas,
                subscription=TenantSubscriptionConfig(
                    tier=plan_id.lower(),
                ),
            )
    return TenantBillingPlanSchema(plan_id=plan_id.lower())


def catalog_public() -> list[dict[str, Any]]:
    """Public plan list. Rates appear only if operators configured them in env."""
    out = []
    for entry in load_plan_catalog():
        out.append(
            {
                "id": entry.get("id"),
                "display_name": entry.get("display_name") or entry.get("id"),
                "quotas": entry.get("quotas") or {},
                "currency": entry.get("currency") or "KES",
                "features": entry.get("features") or _default_features(str(entry.get("id"))),
                "has_configured_rates": bool(entry.get("rates")),
            }
        )
    return out


def _default_features(plan_id: str) -> list[str]:
    base = ["kenyan_receptionist", "whatsapp", "mpesa"]
    extras = {
        "starter": [],
        "growth": ["campaigns", "api_keys"],
        "business": ["campaigns", "api_keys", "webhooks", "audit_logs"],
        "enterprise": [
            "campaigns",
            "api_keys",
            "webhooks",
            "audit_logs",
            "sso",
            "custom_domain",
            "white_label",
            "dedicated_numbers",
            "dedicated_infrastructure",
            "sla_metrics",
        ],
    }
    return base + extras.get(plan_id, extras["starter"])
