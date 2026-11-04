"""Tests for multi-tenant usage billing."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.services.tenant_billing.collectors import CallMinutesCollector, MpesaUsageCollector
from api.services.tenant_billing.invoicing import TenantInvoiceGenerator
from api.services.tenant_billing.ledger import UsageLedger
from api.services.tenant_billing.quota import TenantQuotaEnforcer
from api.services.tenant_billing.schema import TenantUsageRates
from api.services.tenant_billing.types import UsageMetric, UsageRecordRequest


def test_usage_ledger_prices_call_minutes():
    ledger = UsageLedger()
    amount = ledger._price(UsageMetric.CALL_MINUTES, 10.0, TenantUsageRates(per_minute_usd=0.02))
    assert amount == 0.2


def test_usage_ledger_prices_stt():
    ledger = UsageLedger()
    amount = ledger._price(UsageMetric.STT_SECONDS, 120.0, TenantUsageRates(stt_per_minute_usd=0.006))
    assert amount > 0


@pytest.mark.asyncio
async def test_call_collector_skips_without_duration():
    collector = CallMinutesCollector()
    with patch("api.services.tenant_billing.collectors.db_client") as mock_db:
        mock_run = AsyncMock()
        mock_run.workflow.organization_id = 1
        mock_run.usage_info = {}
        mock_db.get_workflow_run_by_id = AsyncMock(return_value=mock_run)
        assert await collector.from_workflow_run(99) is False


@pytest.mark.asyncio
async def test_mpesa_collector_skips_pending():
    collector = MpesaUsageCollector()
    tx = AsyncMock()
    tx.status = "pending"
    assert await collector.from_transaction(tx) is False


@pytest.mark.asyncio
async def test_quota_allows_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "api.services.tenant_billing.quota.TENANT_USAGE_BILLING_ENABLED", False
    )
    enforcer = TenantQuotaEnforcer()
    outcome = await enforcer.check(1, UsageMetric.CALL_MINUTES)
    assert outcome.allowed is True


@pytest.mark.asyncio
async def test_ledger_record_skips_duplicate():
    ledger = UsageLedger()
    with (
        patch("api.services.tenant_billing.ledger.TENANT_USAGE_BILLING_ENABLED", True),
        patch("api.services.tenant_billing.ledger.load_billing_plan", new_callable=AsyncMock),
        patch("api.services.tenant_billing.ledger.db_client") as mock_db,
    ):
        mock_db.record_usage_event = AsyncMock(return_value=None)
        result = await ledger.record(
            UsageRecordRequest(
                organization_id=1,
                metric=UsageMetric.CALL_MINUTES,
                quantity=1.0,
                aggregation_key="test:1",
            )
        )
    assert result is False


def test_invoice_unit_prices():
    gen = TenantInvoiceGenerator()
    rates = TenantUsageRates(per_minute_usd=0.05)
    assert gen._unit_price(UsageMetric.CALL_MINUTES.value, rates) == 0.05
