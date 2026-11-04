"""Debt collection marketplace listing."""

from __future__ import annotations

from dataclasses import replace

from api.services.debt_collection.template import KENYA_DEBT_COLLECTION
from api.services.template_marketplace.schema import MarketplaceTemplateListing, TemplateVersionInfo

DEBT_COLLECTION_TEMPLATE = replace(
    KENYA_DEBT_COLLECTION,
    template_id="debt_collection",
)

DEBT_COLLECTION_LISTING = MarketplaceTemplateListing(
    template_id="debt_collection",
    template=DEBT_COLLECTION_TEMPLATE,
    tags=("debt", "collections", "mpesa", "recovery", "finance"),
    search_keywords=(
        "debt",
        "collection",
        "loan",
        "repayment",
        "mkopo",
        "deni",
        "installment",
        "negotiation",
    ),
    category="finance",
    featured=True,
    icon="scale",
    version_history=(
        TemplateVersionInfo(
            version="1.0.0",
            released_at="2026-05-01",
            changelog="Multilingual debt collection with M-Pesa, installments, and compliance guardrails.",
        ),
    ),
)
