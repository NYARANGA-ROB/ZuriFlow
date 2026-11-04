"""Tests for the Kenyan SME/enterprise SaaS control plane."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.db.models import OrganizationModel, UserModel
from api.services.control_plane.business_tools import list_business_tools
from api.services.control_plane.knowledge import retrieve_relevant_knowledge
from api.services.control_plane.setup import OrganizationSetupProfile
from api.services.control_plane.workflows import builder_catalog, promote_environment


@pytest.fixture
async def org_and_user(async_session):
    org = OrganizationModel(provider_id="test-org-control-plane")
    async_session.add(org)
    await async_session.flush()
    user = UserModel(
        provider_id="test-user-control-plane", selected_organization_id=org.id
    )
    async_session.add(user)
    await async_session.flush()
    return org, user


def test_setup_profile_tracks_required_sme_fields():
    incomplete = OrganizationSetupProfile()
    report = incomplete.completeness()
    assert report["ready"] is False
    assert report["total"] == 10

    complete = OrganizationSetupProfile(
        business_name="Kibera Mart",
        industry="retail",
        location="Kibera",
        county="Nairobi",
        phone_numbers=[{"label": "main", "number": "+254712345678", "purpose": "inbound"}],
        languages=["en", "sw"],
        payment={"mpesa_enabled": True, "paybill": "123456"},
        escalation_contacts=[{"name": "Amina", "phone": "+254700000000", "role": "supervisor"}],
    )
    assert complete.completeness()["ready"] is True


def test_business_tool_catalog_covers_requested_operations():
    keys = {item["key"] for item in list_business_tools()}
    assert {
        "appointment_booking",
        "order_lookup",
        "customer_lookup",
        "payment",
        "delivery_tracking",
        "crm_lookup",
        "ticket_creation",
        "human_transfer",
        "sms",
        "whatsapp",
    } <= keys


def test_workflow_builder_exposes_nodes_templates_and_environments():
    catalog = builder_catalog()
    assert catalog["environments"] == ["draft", "testing", "staging", "published"]
    assert catalog["reusable_nodes"]
    assert catalog["templates"]
    assert catalog["variables"]


@pytest.mark.asyncio
async def test_knowledge_retrieval_returns_matches_not_the_full_store():
    rows = [
        SimpleNamespace(
            category="faq",
            title="Opening hours",
            content="Weekdays 8 to 5",
        ),
        SimpleNamespace(
            category="policy",
            title="Returns",
            content="7 day return window",
        ),
    ]
    with patch("api.services.control_plane.knowledge.db_client") as db:
        db.search_business_knowledge_entries = AsyncMock(return_value=rows[:1])
        hits = await retrieve_relevant_knowledge(1, "hours")
    assert len(hits) == 1
    assert "Opening hours" in hits[0]["text"]
    assert "Returns" not in hits[0]["text"]
    db.search_business_knowledge_entries.assert_awaited()


@pytest.mark.asyncio
async def test_production_promotion_requires_staging():
    draft = SimpleNamespace(
        status="draft",
        workflow_json={"nodes": []},
        workflow_configurations={},
        template_context_variables={},
    )
    with patch("api.services.control_plane.workflows.db_client") as db:
        db.get_workflow_versions = AsyncMock(return_value=[draft])
        with pytest.raises(ValueError, match="staging"):
            await promote_environment(
                9, "published", organization_id=1, user_id=2, changelog="go live"
            )


@pytest.mark.asyncio
async def test_knowledge_and_audit_tables_are_org_scoped(db_session, org_and_user):
    org, user = org_and_user
    entry = await db_session.create_business_knowledge_entry(
        organization_id=org.id,
        category="faq",
        title="M-Pesa paybill",
        content="Paybill 123456",
        created_by_user_id=user.id,
    )
    hits = await db_session.search_business_knowledge_entries(org.id, "paybill")
    assert [row.id for row in hits] == [entry.id]

    log = await db_session.append_organization_audit_log(
        organization_id=org.id,
        action="agent_published",
        resource_type="workflow",
        actor_user_id=user.id,
        resource_id="1",
        summary="Published v2",
    )
    logs = await db_session.list_organization_audit_logs(org.id)
    assert logs[0].id == log.id
    assert logs[0].action == "agent_published"
