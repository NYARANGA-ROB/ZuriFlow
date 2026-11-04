"""Kenya-focused industry catalog for the agent marketplace wizard."""

from __future__ import annotations

from dataclasses import dataclass

from api.services.vertical_workflows.registry import get_vertical_workflow_registry
from api.services.vertical_workflows.templates.kenya_marketplace import KENYA_INDUSTRY_SPECS


@dataclass(frozen=True)
class IndustryOption:
    industry_id: str
    name: str
    description: str
    icon: str
    recommended_template_id: str | None
    supports_mpesa: bool
    default_locale: str
    example_use_cases: tuple[str, ...]
    business_type: str = ""


def _from_specs() -> tuple[IndustryOption, ...]:
    options: list[IndustryOption] = []
    for spec in KENYA_INDUSTRY_SPECS:
        options.append(
            IndustryOption(
                industry_id=spec.industry_id,
                name=spec.name,
                description=spec.description,
                icon=spec.icon,
                recommended_template_id=f"kenya_mp_{spec.industry_id}",
                supports_mpesa=spec.mpesa,
                default_locale="mixed",
                example_use_cases=spec.use_cases,
                business_type=spec.business_type,
            )
        )
    return tuple(options)


KENYA_INDUSTRIES: tuple[IndustryOption, ...] = _from_specs()

INDUSTRY_ALIASES: dict[str, str] = {
    "fintech_kenya": "banking",
    "retail": "ecommerce",
    "healthcare": "hospitals",
    "hospitality": "hotels",
    "general": "contact_center",
    "education": "schools",
    "debt_collection": "microfinance",
    "logistics": "logistics",
    "sacco": "sacco",
}


def list_industry_options() -> list[dict]:
    registry = get_vertical_workflow_registry()
    if registry.get("kenya_debt_collection") is None:
        try:
            from api.services.debt_collection.template import KENYA_DEBT_COLLECTION

            registry.register(KENYA_DEBT_COLLECTION)
        except ImportError:
            pass
    items: list[dict] = []
    for opt in KENYA_INDUSTRIES:
        template = registry.get(opt.recommended_template_id) if opt.recommended_template_id else None
        items.append(
            {
                "industry_id": opt.industry_id,
                "name": opt.name,
                "description": opt.description,
                "icon": opt.icon,
                "recommended_template_id": opt.recommended_template_id,
                "template_name": template.name if template else None,
                "supported_locales": list(template.supported_locales) if template else ["en", "sw", "mixed"],
                "supports_mpesa": opt.supports_mpesa,
                "default_locale": opt.default_locale,
                "example_use_cases": list(opt.example_use_cases),
                "business_type": opt.business_type,
            }
        )
    return items


def get_industry_option(industry_id: str) -> IndustryOption | None:
    resolved = INDUSTRY_ALIASES.get(industry_id, industry_id)
    for opt in KENYA_INDUSTRIES:
        if opt.industry_id == industry_id or opt.industry_id == resolved:
            return opt
    return None
