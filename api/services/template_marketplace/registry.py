"""Searchable versioned template registry for the marketplace."""

from __future__ import annotations

from api.services.template_marketplace.schema import (
    MarketplaceTemplateListing,
    TemplateSearchQuery,
    TemplateVersionInfo,
    TemplateVersionStatus,
)
from api.services.template_marketplace.templates.clinic_receptionist import (
    CLINIC_RECEPTIONIST_LISTING,
)
from api.services.template_marketplace.templates.debt_collection import (
    DEBT_COLLECTION_LISTING,
)
from api.services.template_marketplace.templates.logistics_dispatch import (
    LOGISTICS_DISPATCH_LISTING,
)
from api.services.template_marketplace.templates.sacco_collections import (
    SACCO_COLLECTIONS_LISTING,
)
from api.services.template_marketplace.templates.school_fee_reminders import (
    SCHOOL_FEE_REMINDERS_LISTING,
)
from api.services.vertical_workflows.templates.kenya_marketplace import (
    kenya_marketplace_listings,
)
from api.services.vertical_workflows.schema import VerticalIndustry, VerticalWorkflowTemplate

_BUILTIN_LISTINGS: tuple[MarketplaceTemplateListing, ...] = (
    DEBT_COLLECTION_LISTING,
    CLINIC_RECEPTIONIST_LISTING,
    SACCO_COLLECTIONS_LISTING,
    LOGISTICS_DISPATCH_LISTING,
    SCHOOL_FEE_REMINDERS_LISTING,
    *kenya_marketplace_listings(),
)


class TemplateMarketplaceRegistry:
    """In-process registry of marketplace listings with version history."""

    def __init__(self) -> None:
        self._listings: dict[str, MarketplaceTemplateListing] = {}
        self._versions: dict[str, dict[str, VerticalWorkflowTemplate]] = {}

    def register(self, listing: MarketplaceTemplateListing) -> None:
        self._listings[listing.template_id] = listing
        version_map = self._versions.setdefault(listing.template_id, {})
        version_map[listing.template.version] = listing.template
        for ver in listing.version_history:
            if ver.version not in version_map:
                version_map[ver.version] = listing.template

    def get_listing(self, template_id: str) -> MarketplaceTemplateListing | None:
        return self._listings.get(template_id)

    def require_listing(self, template_id: str) -> MarketplaceTemplateListing:
        listing = self.get_listing(template_id)
        if listing is None:
            raise KeyError(f"Marketplace template not found: {template_id}")
        return listing

    def get_version(self, template_id: str, version: str) -> VerticalWorkflowTemplate | None:
        return self._versions.get(template_id, {}).get(version)

    def require_version(
        self, template_id: str, version: str | None = None
    ) -> VerticalWorkflowTemplate:
        listing = self.require_listing(template_id)
        ver = version or listing.latest_version
        tpl = self.get_version(template_id, ver)
        if tpl is None:
            raise KeyError(f"Template version not found: {template_id}@{ver}")
        return tpl

    def list_versions(self, template_id: str) -> list[TemplateVersionInfo]:
        listing = self.require_listing(template_id)
        return list(listing.version_history)

    def list_listings(self) -> list[MarketplaceTemplateListing]:
        return sorted(self._listings.values(), key=lambda l: (not l.featured, l.template.name))

    def search(self, query: TemplateSearchQuery) -> list[MarketplaceTemplateListing]:
        items = self.list_listings()
        q = query.q.strip().lower()

        def matches(item: MarketplaceTemplateListing) -> bool:
            if query.featured_only and not item.featured:
                return False
            if query.industry and item.template.industry.value != query.industry:
                return False
            if query.category and item.category != query.category:
                return False
            if query.tag and query.tag not in item.tags:
                return False
            if query.locale and query.locale not in item.template.supported_locales:
                return False
            if not q:
                return True
            haystack = " ".join(
                [
                    item.template_id,
                    item.template.name,
                    item.template.description,
                    item.category,
                    *item.tags,
                    *item.search_keywords,
                ]
            ).lower()
            return q in haystack or any(word in haystack for word in q.split())

        filtered = [i for i in items if matches(i)]
        return filtered[: query.limit]


_registry: TemplateMarketplaceRegistry | None = None


def get_template_marketplace_registry() -> TemplateMarketplaceRegistry:
    global _registry
    if _registry is None:
        _registry = TemplateMarketplaceRegistry()
        for listing in _BUILTIN_LISTINGS:
            _registry.register(listing)
        _sync_vertical_registry(_registry)
    return _registry


def _sync_vertical_registry(marketplace: TemplateMarketplaceRegistry) -> None:
    """Register marketplace templates into the vertical workflow registry."""
    from api.services.vertical_workflows.registry import get_vertical_workflow_registry

    vertical = get_vertical_workflow_registry()
    for listing in marketplace.list_listings():
        vertical.register(listing.template)
