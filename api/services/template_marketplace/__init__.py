"""Industry workflow template marketplace."""

from api.services.template_marketplace.schema import TemplateSearchQuery, TenantTemplateCustomization

__all__ = [
    "TemplateSearchQuery",
    "TenantTemplateCustomization",
    "get_template_customization_engine",
    "get_template_marketplace_registry",
    "list_categories",
    "list_tags",
    "search_templates",
]

_LAZY_EXPORTS = {
    "get_template_customization_engine": "api.services.template_marketplace.customization",
    "get_template_marketplace_registry": "api.services.template_marketplace.registry",
    "list_categories": "api.services.template_marketplace.catalog",
    "list_tags": "api.services.template_marketplace.catalog",
    "search_templates": "api.services.template_marketplace.catalog",
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(_LAZY_EXPORTS[name])
    return getattr(module, name)
