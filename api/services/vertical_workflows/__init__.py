"""Vertical workflow architecture for AI business agents."""

from api.services.vertical_workflows.schema import VerticalIndustry, VerticalWorkflowTemplate

__all__ = [
    "BusinessRuleEngine",
    "VerticalIndustry",
    "VerticalTemplateLoader",
    "VerticalWorkflowEngine",
    "VerticalWorkflowRegistry",
    "VerticalWorkflowTemplate",
    "get_business_rule_engine",
    "get_vertical_template_loader",
    "get_vertical_workflow_engine",
    "get_vertical_workflow_registry",
]

_LAZY_EXPORTS = {
    "BusinessRuleEngine": "api.services.vertical_workflows.rules",
    "get_business_rule_engine": "api.services.vertical_workflows.rules",
    "VerticalTemplateLoader": "api.services.vertical_workflows.loader",
    "get_vertical_template_loader": "api.services.vertical_workflows.loader",
    "VerticalWorkflowEngine": "api.services.vertical_workflows.engine",
    "get_vertical_workflow_engine": "api.services.vertical_workflows.engine",
    "VerticalWorkflowRegistry": "api.services.vertical_workflows.registry",
    "get_vertical_workflow_registry": "api.services.vertical_workflows.registry",
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(_LAZY_EXPORTS[name])
    return getattr(module, name)
