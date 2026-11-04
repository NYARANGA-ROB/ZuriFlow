"""Search facade for the template marketplace."""

from __future__ import annotations

from api.services.template_marketplace.registry import get_template_marketplace_registry
from api.services.template_marketplace.schema import MarketplaceTemplateListing, TemplateSearchQuery


def search_templates(query: TemplateSearchQuery) -> list[dict]:
    registry = get_template_marketplace_registry()
    return [item.to_summary_dict() for item in registry.search(query)]


def list_categories() -> list[str]:
    registry = get_template_marketplace_registry()
    cats = {item.category for item in registry.list_listings()}
    return sorted(cats)


def list_tags() -> list[str]:
    registry = get_template_marketplace_registry()
    tags: set[str] = set()
    for item in registry.list_listings():
        tags.update(item.tags)
    return sorted(tags)
