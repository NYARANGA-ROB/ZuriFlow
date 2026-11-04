"""Tests for the industry template marketplace."""

from __future__ import annotations

import pytest

from api.services.template_marketplace.catalog import list_categories, list_tags, search_templates
from api.services.template_marketplace.org_config import normalize_org_config
from api.services.template_marketplace.schema import TenantTemplateCustomization
from api.services.template_marketplace.inheritance import get_template_inheritance_resolver
from api.services.template_marketplace.registry import get_template_marketplace_registry
from api.services.template_marketplace.schema import TemplateSearchQuery


@pytest.fixture(autouse=True)
def _init_registry():
    get_template_marketplace_registry()


class TestRegistry:
    def test_lists_core_and_kenya_marketplace_templates(self):
        registry = get_template_marketplace_registry()
        ids = {l.template_id for l in registry.list_listings()}
        assert {
            "debt_collection",
            "clinic_receptionist",
            "sacco_collections",
            "logistics_dispatch",
            "school_fee_reminders",
        }.issubset(ids)
        kenya = {i for i in ids if i.startswith("kenya_mp_")}
        assert len(kenya) == 25

    def test_search_by_keyword(self):
        results = search_templates(TemplateSearchQuery(q="sacco"))
        assert any(r["template_id"] == "sacco_collections" for r in results)

    def test_pinned_version_survives_catalog_updates(self):
        registry = get_template_marketplace_registry()
        listing = registry.require_listing("kenya_mp_sacco")
        pinned = registry.require_version("kenya_mp_sacco", listing.latest_version)
        assert pinned.version == listing.latest_version
        assert pinned.template_id == "kenya_mp_sacco"

    def test_search_by_industry(self):
        results = search_templates(TemplateSearchQuery(industry="education"))
        assert any(r["template_id"] == "school_fee_reminders" for r in results)

    def test_version_history(self):
        registry = get_template_marketplace_registry()
        versions = registry.list_versions("debt_collection")
        assert versions[0].version == "1.0.0"


class TestInheritance:
    def test_sacco_inherits_debt_collection_steps(self):
        registry = get_template_marketplace_registry()
        child = registry.require_version("sacco_collections")
        resolver = get_template_inheritance_resolver()
        resolved = resolver.resolve(child)
        step_ids = {s.step_id for s in resolved.steps}
        assert "greeting" in step_ids
        assert "collect_payment" in step_ids or "collections" in step_ids
        assert resolved.extends_template_id == "debt_collection"


class TestCustomization:
    def test_normalize_legacy_flat_config(self):
        raw = {
            "debt_collection": {"default_locale": "sw"},
            "other": "ignored",
        }
        normalized = normalize_org_config(raw)
        assert normalized["templates"]["debt_collection"]["default_locale"] == "sw"

    def test_apply_prompt_override(self):
        from api.services.template_marketplace.customization import (
            TemplateCustomizationEngine,
        )

        registry = get_template_marketplace_registry()
        base = registry.require_version("clinic_receptionist")
        engine = TemplateCustomizationEngine()
        custom = TenantTemplateCustomization(
            template_id="clinic_receptionist",
            prompt_overrides={
                "greeting": {"en": "Welcome to Nairobi West Clinic."},
            },
        )
        merged = engine.apply_customization(base, custom)
        greeting = merged.step("greeting")
        assert greeting is not None
        assert "Nairobi West" in greeting.prompts.system["en"]
