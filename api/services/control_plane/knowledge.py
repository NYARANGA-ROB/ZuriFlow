"""Structured business knowledge that agents retrieve on demand."""

from __future__ import annotations

from typing import Any

from api.db import db_client
from api.db.models import BusinessKnowledgeEntryModel

KNOWLEDGE_CATEGORIES = (
    "faq",
    "product",
    "service",
    "pricing",
    "location",
    "hours",
    "policy",
    "document",
    "staff",
)


def serialize_entry(row: BusinessKnowledgeEntryModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "category": row.category,
        "title": row.title,
        "content": row.content,
        "metadata": row.metadata_json or {},
        "document_uuid": row.document_uuid,
        "is_active": row.is_active,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def retrieve_relevant_knowledge(
    organization_id: int, query: str, *, limit: int = 3
) -> list[dict[str, Any]]:
    """Return only matching snippets — never the full knowledge base."""
    if not query or not query.strip():
        return []
    rows = await db_client.search_business_knowledge_entries(
        organization_id, query, limit=limit
    )
    return [
        {
            "text": f"[{row.category}] {row.title}: {row.content}"[:1500],
            "filename": row.title,
            "similarity": 0.82,
            "chunk_index": 0,
            "source": "business_knowledge",
            "category": row.category,
        }
        for row in rows
    ]
