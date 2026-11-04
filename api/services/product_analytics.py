"""Product funnel: activation, first agent, first call, first payment, churn signals."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client

FUNNEL = (
    "activation",
    "first_agent_created",
    "first_successful_call",
    "first_payment",
)


async def track_once(
    organization_id: int,
    event_name: str,
    *,
    properties: dict[str, Any] | None = None,
) -> None:
    try:
        if await db_client.has_product_event(organization_id, event_name):
            return
        await db_client.insert_product_event(
            organization_id=organization_id,
            event_name=event_name,
            properties=properties or {},
        )
    except Exception as exc:
        logger.debug("product analytics skipped {}: {}", event_name, exc)


async def track(
    organization_id: int,
    event_name: str,
    *,
    properties: dict[str, Any] | None = None,
) -> None:
    try:
        await db_client.insert_product_event(
            organization_id=organization_id,
            event_name=event_name,
            properties=properties or {},
        )
    except Exception as exc:
        logger.debug("product analytics skipped {}: {}", event_name, exc)


async def funnel(organization_id: int) -> dict[str, Any]:
    counts = await db_client.count_product_events(organization_id)
    steps = []
    for name in FUNNEL:
        steps.append(
            {
                "event": name,
                "completed": counts.get(name, 0) > 0,
                "count": counts.get(name, 0),
            }
        )
    failed_onboarding = counts.get("failed_onboarding", 0)
    usage_growth = counts.get("usage_growth", 0)
    churn = counts.get("churn_indicator", 0)
    activated = steps[0]["completed"]
    retained = steps[2]["completed"]
    return {
        "organization_id": organization_id,
        "funnel": steps,
        "failed_onboarding": failed_onboarding,
        "usage_growth_events": usage_growth,
        "churn_indicators": churn,
        "agent_retention": retained and steps[1]["completed"],
        "activated": activated,
        "note": "Internal product analytics. Not a contractual SLA.",
    }
