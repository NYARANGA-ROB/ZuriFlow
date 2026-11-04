"""Usage quota enforcement per tenant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from api.constants import TENANT_USAGE_BILLING_ENABLED
from api.db import db_client
from api.services.tenant.config import load_tenant_configuration
from api.services.tenant_billing.plan import load_billing_plan
from api.services.tenant_billing.types import QuotaCheckOutcome, QuotaEnforcement, UsageMetric


class TenantQuotaEnforcer:
    """Check tenant usage against configured quotas before billable operations."""

    async def check(
        self,
        organization_id: int,
        metric: UsageMetric,
        *,
        delta: float = 0.0,
    ) -> QuotaCheckOutcome:
        if not TENANT_USAGE_BILLING_ENABLED:
            return QuotaCheckOutcome(
                allowed=True,
                metric_code=metric.value,
                used=0.0,
                limit=None,
                enforcement=QuotaEnforcement.NONE.value,
            )

        limit, enforcement = await self._resolve_limit(organization_id, metric)
        if limit is None:
            return QuotaCheckOutcome(
                allowed=True,
                metric_code=metric.value,
                used=0.0,
                limit=None,
                enforcement=enforcement,
            )

        period_start, period_end = self._current_month_window()
        used = await db_client.sum_usage(
            organization_id,
            metric_code=metric.value,
            from_ts=period_start,
            to_ts=period_end,
        )
        projected = used + delta
        exceeded = projected > limit
        allowed = not exceeded or enforcement != QuotaEnforcement.HARD.value

        message = ""
        if exceeded and enforcement == QuotaEnforcement.HARD.value:
            message = (
                f"Quota exceeded for {metric.value}: "
                f"{projected:.2f} / {limit:.2f} this billing period."
            )
        elif exceeded:
            message = (
                f"Soft quota warning for {metric.value}: "
                f"{projected:.2f} / {limit:.2f}."
            )

        return QuotaCheckOutcome(
            allowed=allowed,
            metric_code=metric.value,
            used=used,
            limit=limit,
            enforcement=enforcement,
            error_message=message,
        )

    async def list_quotas(self, organization_id: int) -> list[dict[str, Any]]:
        period_start, period_end = self._current_month_window()
        db_quotas = await db_client.list_quotas(organization_id)
        plan = await load_billing_plan(organization_id)
        config_limits = {
            UsageMetric.CALL_MINUTES.value: plan.quotas.call_minutes_monthly,
            UsageMetric.STT_SECONDS.value: (
                plan.quotas.stt_minutes_monthly * 60
                if plan.quotas.stt_minutes_monthly is not None
                else None
            ),
            UsageMetric.WHATSAPP_OUTBOUND.value: plan.quotas.whatsapp_messages_monthly,
            UsageMetric.CONCURRENT_CALLS.value: plan.quotas.concurrent_calls,
            UsageMetric.WORKFLOWS.value: plan.quotas.workflows,
            UsageMetric.AGENTS.value: plan.quotas.agents,
            UsageMetric.USERS.value: plan.quotas.users,
            UsageMetric.STORAGE_GB.value: plan.quotas.storage_gb,
            UsageMetric.INTEGRATIONS.value: plan.quotas.integrations,
        }

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        tenant_config = await load_tenant_configuration(organization_id)
        default_enforcement = tenant_config.billing.quota_enforcement

        for quota in db_quotas:
            seen.add(quota.metric_code)
            used = await db_client.sum_usage(
                organization_id,
                metric_code=quota.metric_code,
                from_ts=period_start,
                to_ts=period_end,
            )
            rows.append(self._quota_row(quota.metric_code, quota.limit_quantity, used, quota.enforcement))

        for metric_code, limit in config_limits.items():
            if metric_code in seen or limit is None:
                continue
            used = await db_client.sum_usage(
                organization_id,
                metric_code=metric_code,
                from_ts=period_start,
                to_ts=period_end,
            )
            rows.append(self._quota_row(metric_code, limit, used, default_enforcement))

        return rows

    async def upsert_quota(
        self,
        organization_id: int,
        *,
        metric_code: str,
        limit_quantity: float,
        period: str = "monthly",
        enforcement: str = "soft",
    ) -> dict[str, Any]:
        quota = await db_client.upsert_quota(
            organization_id=organization_id,
            metric_code=metric_code,
            limit_quantity=limit_quantity,
            period=period,
            enforcement=enforcement,
        )
        period_start, period_end = self._current_month_window()
        used = await db_client.sum_usage(
            organization_id,
            metric_code=metric_code,
            from_ts=period_start,
            to_ts=period_end,
        )
        return self._quota_row(metric_code, quota.limit_quantity, used, quota.enforcement)

    async def _resolve_limit(
        self, organization_id: int, metric: UsageMetric
    ) -> tuple[float | None, str]:
        quota = await db_client.get_quota(organization_id, metric.value)
        if quota:
            return quota.limit_quantity, quota.enforcement

        plan = await load_tenant_configuration(organization_id)
        enforcement = plan.billing.quota_enforcement
        billing_plan = await load_billing_plan(organization_id)
        q = billing_plan.quotas
        if metric == UsageMetric.CALL_MINUTES:
            return q.call_minutes_monthly, enforcement
        if metric == UsageMetric.STT_SECONDS and q.stt_minutes_monthly is not None:
            return q.stt_minutes_monthly * 60.0, enforcement
        if metric in {UsageMetric.WHATSAPP_INBOUND, UsageMetric.WHATSAPP_OUTBOUND}:
            return q.whatsapp_messages_monthly, enforcement
        if metric == UsageMetric.CONCURRENT_CALLS:
            return q.concurrent_calls, enforcement
        if metric == UsageMetric.WORKFLOWS:
            return q.workflows, enforcement
        if metric == UsageMetric.AGENTS:
            return q.agents or q.workflows, enforcement
        if metric == UsageMetric.USERS:
            return q.users, enforcement
        if metric == UsageMetric.STORAGE_GB:
            return q.storage_gb, enforcement
        if metric == UsageMetric.INTEGRATIONS:
            return q.integrations, enforcement
        return None, enforcement

    @staticmethod
    def _current_month_window() -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start + relativedelta(months=1)
        return start, end

    @staticmethod
    def _quota_row(
        metric_code: str, limit: float, used: float, enforcement: str
    ) -> dict[str, Any]:
        remaining = max(limit - used, 0.0)
        return {
            "metric_code": metric_code,
            "period": "monthly",
            "limit_quantity": limit,
            "used_quantity": round(used, 4),
            "remaining_quantity": round(remaining, 4),
            "enforcement": enforcement,
            "exceeded": used > limit,
        }


_enforcer: TenantQuotaEnforcer | None = None


def get_tenant_quota_enforcer() -> TenantQuotaEnforcer:
    global _enforcer
    if _enforcer is None:
        _enforcer = TenantQuotaEnforcer()
    return _enforcer
