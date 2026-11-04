"""Tests for conversation intelligence, insights, and privacy-aware dashboards."""

from __future__ import annotations

from api.services.business_intelligence.aggregator import aggregate_intelligence
from api.services.business_intelligence.classifier import classify_conversation
from api.services.business_intelligence.dashboards import compose_dashboard
from api.services.business_intelligence.insights import build_insights
from api.services.business_intelligence.privacy import redact_text
from api.services.tenant.rbac import permissions_for_role
from api.services.tenant.types import Permission, TenantRole


def test_classifier_labels_mpesa_payment_and_redacts_phone():
    result = classify_conversation(
        "Nataka kulipa na M-Pesa paybill, nisaidie. Call me on 0712345678",
        completed=False,
    )
    assert result.category == "payment"
    assert result.language in {"sw", "sheng"}
    assert result.redacted_excerpt
    assert "0712345678" not in result.redacted_excerpt
    assert "[phone]" in result.redacted_excerpt


def test_classifier_marks_escalation_and_transfer():
    result = classify_conversation(
        "I need a supervisor now, transfer me to a human agent",
        transferred=True,
        completed=False,
    )
    assert result.category == "escalation"
    assert result.transferred is True
    assert result.contained is False
    assert result.first_contact_resolved is False


def test_redact_text_strips_email_and_id():
    text = redact_text("Email jane@shop.co.ke id 12345678")
    assert "[email]" in text
    assert "[id]" in text
    assert "jane@" not in text


def test_aggregate_core_and_kenyan_kpis():
    snap = aggregate_intelligence(
        call_stats={"total_calls": 10, "completed_calls": 7, "avg_duration_s": 90},
        payment_stats={
            "attempts": 5,
            "success_count": 3,
            "failed_count": 1,
            "abandoned_count": 1,
            "kes_processed": 4500,
        },
        classifications=[
            {
                "category": "payment",
                "intent": "pay_bill",
                "sentiment": "negative",
                "language": "sw",
                "contained": True,
                "transferred": False,
                "first_contact_resolved": True,
                "requested_product": "loan",
                "code_switched": True,
                "county": "Nairobi",
            },
            {
                "category": "inquiry",
                "intent": "hours",
                "sentiment": "neutral",
                "language": "en",
                "contained": True,
                "transferred": False,
                "first_contact_resolved": True,
                "requested_product": "loan",
                "code_switched": False,
                "county": "Kisumu",
            },
            {
                "category": "escalation",
                "intent": "pay_bill",
                "sentiment": "negative",
                "language": "sw",
                "contained": False,
                "transferred": True,
                "first_contact_resolved": False,
                "requested_product": None,
                "code_switched": True,
            },
        ],
        kenya={"language_distribution": {"sw": 8, "en": 2, "sheng": 1}},
        channels={"sms_followup_rate": 0.4, "whatsapp_followup_rate": 0.6},
        previous_payments={"failed_count": 0},
    )
    assert snap["core"]["total_calls"] == 10
    assert snap["core"]["missed_calls"] == 3
    assert snap["kenyan"]["kes_processed"] == 4500
    assert snap["kenyan"]["payment_success_rate"] == 0.6
    assert snap["top_products"][0][0] == "loan"


def test_insights_cover_language_payments_and_escalation():
    snap = {
        "core": {
            "total_calls": 20,
            "completed_calls": 12,
            "transfer_rate": 0.4,
            "first_contact_resolution": 0.2,
            "intent_distribution": {"pay_bill": 9, "hours": 2},
            "classified_conversations": 11,
        },
        "kenyan": {
            "kiswahili_usage_rate": 0.7,
            "english_usage_rate": 0.2,
            "payment_failures": 6,
            "payment_failures_previous": 1,
        },
        "top_products": [("wifi", 5)],
        "classified_conversations": 11,
    }
    headlines = [item["headline"] for item in build_insights(snap)]
    assert any("wifi" in h for h in headlines)
    assert any("Payment failures" in h for h in headlines)
    assert any("Kiswahili" in h for h in headlines)
    assert any("pay_bill" in h for h in headlines)


def test_payment_dashboard_hides_kes_without_permission():
    snap = aggregate_intelligence(
        call_stats={"total_calls": 1, "completed_calls": 1, "avg_duration_s": 10},
        payment_stats={
            "attempts": 2,
            "success_count": 1,
            "failed_count": 0,
            "abandoned_count": 1,
            "kes_processed": 900,
        },
        classifications=[],
    )
    hidden = compose_dashboard(
        "payments",
        snap,
        [],
        include_payments=False,
        include_excerpts=False,
    )
    assert hidden["kpis"]["kes_processed"] is None
    assert hidden["restricted"] is True
    shown = compose_dashboard(
        "payments",
        snap,
        [],
        include_payments=True,
        include_excerpts=False,
    )
    assert shown["kpis"]["kes_processed"] == 900


def test_conversation_dashboard_strips_excerpts_without_pii_role():
    dash = compose_dashboard(
        "conversation",
        {"core": {}, "top_products": []},
        [],
        include_payments=False,
        include_excerpts=False,
        conversations=[{"category": "support", "redacted_excerpt": "keep secret"}],
    )
    assert "redacted_excerpt" not in dash["conversations"][0]


def test_rbac_payment_and_pii_are_not_on_analyst():
    analyst = permissions_for_role(TenantRole.ANALYST)
    billing = permissions_for_role(TenantRole.BILLING)
    operator = permissions_for_role(TenantRole.OPERATOR)
    assert Permission.ANALYTICS_READ in analyst
    assert Permission.PAYMENT_ANALYTICS_READ not in analyst
    assert Permission.CONVERSATION_PII_READ not in analyst
    assert Permission.PAYMENT_ANALYTICS_READ in billing
    assert Permission.CONVERSATION_PII_READ in operator
    assert Permission.PAYMENT_ANALYTICS_READ in permissions_for_role(TenantRole.OWNER)
