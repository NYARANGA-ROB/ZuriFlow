"""Feature capability matrix for admin operations APIs."""

from __future__ import annotations

from typing import Any

from api.constants import (
    ADMIN_OPERATIONS_ENABLED,
    BUSINESS_CALL_ANALYTICS_ENABLED,
    CALL_RELIABILITY_ENABLED,
    HUMAN_ESCALATION_ENABLED,
    VOICE_CAMPAIGN_ENABLED,
)


def build_capabilities() -> dict[str, Any]:
    return {
        "admin_operations": ADMIN_OPERATIONS_ENABLED,
        "realtime_calls": True,
        "payment_analytics": True,
        "campaign_tracking": VOICE_CAMPAIGN_ENABLED,
        "escalation_tracking": HUMAN_ESCALATION_ENABLED,
        "tenant_analytics": True,
        "workflow_performance": True,
        "business_call_analytics": BUSINESS_CALL_ANALYTICS_ENABLED,
        "call_reliability": CALL_RELIABILITY_ENABLED,
        "endpoints": {
            "summary": "/admin-operations/summary",
            "live_calls": "/admin-operations/calls/live",
            "payments": "/admin-operations/payments/summary",
            "campaigns": "/admin-operations/campaigns",
            "escalations": "/admin-operations/escalations/summary",
            "workflows": "/admin-operations/workflows/performance",
            "search_runs": "/admin-operations/search/runs",
            "search_campaigns": "/admin-operations/search/campaigns",
            "search_payments": "/admin-operations/search/payments",
            "report": "/admin-operations/reports/summary",
            "websocket": "/admin-operations/ws/live",
        },
    }
