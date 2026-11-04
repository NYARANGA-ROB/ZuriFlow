"""Commercial SaaS catalog, ledger fields, and product funnel."""

from __future__ import annotations

from api.services.tenant.schema import TenantBrandingSettings, TenantConfigurationSchema
from api.services.tenant_billing.catalog import PLAN_IDS, catalog_public, plan_from_catalog
from api.services.tenant_billing.ledger import UsageLedger
from api.services.tenant_billing.schema import TenantUsageRates
from api.services.tenant_billing.types import UsageMetric


def test_plan_catalog_includes_four_tiers_without_hardcoded_prices():
    plans = catalog_public()
    ids = {p["id"] for p in plans}
    assert set(PLAN_IDS) <= ids
    for plan in plans:
        assert "rates" not in plan or plan.get("has_configured_rates") in {True, False}
        assert plan["has_configured_rates"] is False


def test_plan_from_catalog_default_rates_are_zero():
    plan = plan_from_catalog("growth")
    assert plan.plan_id == "growth"
    assert plan.rates.per_minute_usd == 0.0
    assert plan.rates.llm_per_1k_tokens_usd == 0.0


def test_ledger_prices_only_from_configured_rates():
    ledger = UsageLedger()
    zero = ledger._price(UsageMetric.LLM_TOKENS, 1000, TenantUsageRates())
    priced = ledger._price(
        UsageMetric.LLM_TOKENS, 1000, TenantUsageRates(llm_per_1k_tokens_usd=2.0)
    )
    assert zero == 0.0
    assert priced == 2.0


def test_new_metrics_have_units():
    from api.services.tenant_billing.types import METRIC_UNITS

    for metric in (
        UsageMetric.PHONE_CALLS,
        UsageMetric.WEB_CALLS,
        UsageMetric.LLM_TOKENS,
        UsageMetric.SMS,
        UsageMetric.STORAGE_GB,
        UsageMetric.CONCURRENT_CALLS,
    ):
        assert metric in METRIC_UNITS


def test_tenant_config_includes_branding_and_enterprise():
    cfg = TenantConfigurationSchema()
    assert cfg.branding == TenantBrandingSettings()
    assert cfg.enterprise.sso_protocol == "none"
    assert cfg.billing.plan_id == "starter"


def test_branding_rejects_nothing_on_empty():
    b = TenantBrandingSettings(agent_display_name="Zuri")
    assert b.agent_display_name == "Zuri"
    assert b.logo_url is None
