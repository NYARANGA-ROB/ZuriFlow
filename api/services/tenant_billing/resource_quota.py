"""Count-based quota checks before creating expensive tenant resources."""

from __future__ import annotations

from fastapi import HTTPException

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.db import db_client
from api.services.tenant_billing.quota import get_tenant_quota_enforcer
from api.services.tenant_billing.types import QuotaEnforcement, UsageMetric


async def assert_resource_quota(organization_id: int, metric: UsageMetric) -> None:
    if not TENANT_USAGE_BILLING_ENABLED:
        return
    used = await _current_count(organization_id, metric)
    outcome = await get_tenant_quota_enforcer().check(
        organization_id, metric, delta=0.0
    )
    if outcome.limit is None:
        return
    enforcement = outcome.enforcement
    if used >= outcome.limit and enforcement == QuotaEnforcement.HARD.value:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Plan quota reached for {metric.value}: "
                f"{used:.0f} / {outcome.limit:.0f}."
            ),
        )


async def assert_call_allowed(organization_id: int, *, web: bool) -> None:
    if not TENANT_USAGE_BILLING_ENABLED:
        return
    minutes = await get_tenant_quota_enforcer().check(
        organization_id, UsageMetric.CALL_MINUTES, delta=1.0
    )
    if not minutes.allowed:
        raise HTTPException(status_code=402, detail=minutes.error_message)
    concurrent = await get_tenant_quota_enforcer().check(
        organization_id, UsageMetric.CONCURRENT_CALLS, delta=1.0
    )
    if concurrent.limit is not None:
        from api.services.campaign.rate_limiter import rate_limiter

        try:
            current = await rate_limiter.get_concurrent_count(organization_id)
        except Exception:
            current = 0
        if current >= concurrent.limit and concurrent.enforcement == QuotaEnforcement.HARD.value:
            raise HTTPException(
                status_code=402,
                detail="Concurrent call quota reached for this billing period.",
            )
    _ = web


async def _current_count(organization_id: int, metric: UsageMetric) -> float:
    if metric in {UsageMetric.WORKFLOWS, UsageMetric.AGENTS}:
        counts = await db_client.get_workflow_counts(organization_id)
        return float(counts.get("active", 0) or 0)
    if metric == UsageMetric.USERS:
        members = await db_client.list_organization_members(organization_id)
        return float(len(members))
    if metric == UsageMetric.INTEGRATIONS:
        rows = await db_client.get_integrations_by_organization_id(organization_id)
        return float(len(rows or []))
    if metric == UsageMetric.STORAGE_GB:
        from datetime import UTC, datetime

        from dateutil.relativedelta import relativedelta

        start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return await db_client.sum_usage(
            organization_id,
            metric_code=UsageMetric.STORAGE_GB.value,
            from_ts=start,
            to_ts=start + relativedelta(months=1),
        )
    return 0.0
