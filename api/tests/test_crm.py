"""Integration tests for customer CRM."""

from __future__ import annotations

import pytest

from api.db.models import OrganizationModel
from api.services.crm.service import CustomerService, get_customer_service


@pytest.fixture
async def org(async_session):
    organization = OrganizationModel(provider_id="test-org-crm")
    async_session.add(organization)
    await async_session.flush()
    return organization


@pytest.fixture
def crm_service() -> CustomerService:
    return get_customer_service()


class TestCustomerService:
    async def test_create_customer_with_debt(self, db_session, org, crm_service):
        profile = await crm_service.create_customer(
            organization_id=org.id,
            phone_e164="+254712345678",
            full_name="Jane Wanjiku",
            preferred_locale="sw",
            secondary_locales=["en"],
            debt_account={
                "account_reference": "LOAN-001",
                "outstanding_balance": 15000.0,
                "days_past_due": 30,
            },
        )
        assert profile.phone_e164 == "+254712345678"
        assert profile.preferred_locale == "sw"
        assert profile.total_outstanding == 15000.0
        assert len(profile.debt_accounts) == 1
        assert profile.debt_accounts[0]["account_reference"] == "LOAN-001"

    async def test_profile_retrieval_includes_history(
        self, db_session, org, crm_service
    ):
        profile = await crm_service.create_customer(
            organization_id=org.id,
            phone_e164="+254700000001",
            full_name="John Kamau",
            preferred_locale="en",
        )
        await crm_service.record_payment(
            profile.id,
            organization_id=org.id,
            amount=500.0,
            receipt_reference="RCP-1",
        )
        await crm_service.record_call(
            profile.id,
            organization_id=org.id,
            phone_e164="+254700000001",
            outcome="answered",
            language="en",
        )
        await crm_service.record_escalation(
            profile.id,
            organization_id=org.id,
            reason="customer_frustrated",
            risk_level="high",
        )

        loaded = await crm_service.get_profile(profile.id, organization_id=org.id)
        assert loaded is not None
        assert len(loaded.payment_history) == 1
        assert len(loaded.call_history) == 1
        assert len(loaded.escalation_history) == 1

    async def test_payment_reduces_debt_balance(self, db_session, org, crm_service):
        profile = await crm_service.create_customer(
            organization_id=org.id,
            phone_e164="+254711111111",
            full_name="Mary Otieno",
            debt_account={
                "account_reference": "LOAN-002",
                "outstanding_balance": 10000.0,
            },
        )
        debt_id = profile.debt_accounts[0]["id"]
        await crm_service.record_payment(
            profile.id,
            organization_id=org.id,
            amount=3000.0,
            debt_account_id=debt_id,
        )
        refreshed = await crm_service.get_profile(profile.id, organization_id=org.id)
        assert refreshed is not None
        assert refreshed.total_outstanding == 7000.0

    async def test_audit_logs_on_mutations(self, db_session, org, crm_service):
        profile = await crm_service.create_customer(
            organization_id=org.id,
            phone_e164="+254722222222",
            full_name="Peter Mwangi",
        )
        await crm_service.get_profile(profile.id, organization_id=org.id)
        logs = await crm_service.list_audit_logs(
            organization_id=org.id,
            customer_id=profile.id,
        )
        actions = {row["action"] for row in logs}
        assert "customer_created" in actions
        assert "profile_viewed" in actions

    async def test_sync_from_debt_collection(self, db_session, org, crm_service):
        profile = await crm_service.sync_from_debt_collection(
            organization_id=org.id,
            phone_e164="+254733333333",
            full_name="Grace Achieng",
            account_reference="LOAN-003",
            outstanding_balance=8000.0,
            days_past_due=15,
            preferred_locale="mixed",
        )
        assert profile.full_name == "Grace Achieng"
        assert profile.total_outstanding == 8000.0

        updated = await crm_service.sync_from_debt_collection(
            organization_id=org.id,
            phone_e164="+254733333333",
            full_name="Grace Achieng",
            account_reference="LOAN-003",
            outstanding_balance=6000.0,
            days_past_due=20,
        )
        assert updated.id == profile.id
        assert updated.total_outstanding == 6000.0

    async def test_multilingual_preferences_update(self, db_session, org, crm_service):
        profile = await crm_service.create_customer(
            organization_id=org.id,
            phone_e164="+254744444444",
            full_name="David Kipchoge",
            preferred_locale="en",
        )
        updated = await crm_service.update_customer(
            profile.id,
            organization_id=org.id,
            preferred_locale="sw",
            secondary_locales=["en", "mixed"],
        )
        assert updated is not None
        assert updated.preferred_locale == "sw"
        assert updated.secondary_locales == ["en", "mixed"]
