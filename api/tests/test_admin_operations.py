"""Tests for admin operations dashboard APIs."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from api.services.admin_operations.capabilities import build_capabilities
from api.services.admin_operations.reporting import export_summary_csv, export_summary_json
from api.services.admin_operations.search import AdminSearchService
from api.services.admin_operations.service import AdminOperationsService


def test_capabilities_lists_core_modules():
    caps = build_capabilities()
    assert caps["admin_operations"] is True
    assert caps["realtime_calls"] is True
    assert caps["payment_analytics"] is True
    assert "/admin-operations/summary" == caps["endpoints"]["summary"]


def test_export_summary_json_roundtrip():
    summary = {
        "organization_id": 42,
        "from_ts": 1000.0,
        "to_ts": 2000.0,
        "live_calls": {"active_audio_sessions": 2},
    }
    buf, filename = export_summary_json(summary)
    data = json.loads(buf.getvalue().decode("utf-8"))
    assert data["organization_id"] == 42
    assert filename.endswith(".json")


def test_export_summary_csv_contains_sections():
    summary = {
        "organization_id": 7,
        "from_ts": 1.0,
        "to_ts": 2.0,
        "live_calls": {"active_audio_sessions": 1, "incomplete_workflow_runs": 3},
        "payments": {"mpesa": {"transaction_count": 5, "collected_amount": 1000}},
        "workflow_performance": {"total_runs": 10, "completion_rate": 0.8},
        "tenant": {"total_calls": 10, "member_count": 2, "active_workflows": 1},
        "campaigns": {"total": 4},
    }
    buf, filename = export_summary_csv(summary)
    body = buf.getvalue()
    assert "live_calls" in body
    assert "payments" in body
    assert filename.endswith(".csv")


@pytest.mark.asyncio
async def test_search_runs_delegates_to_db():
    svc = AdminSearchService()
    with patch("api.services.admin_operations.search.db_client") as mock_db:
        mock_db.search_workflow_runs = AsyncMock(return_value=([{"id": 1}], 1))
        result = await svc.search_runs(99, q="2547", limit=10)
    assert result["total"] == 1
    assert result["results"][0]["id"] == 1
    mock_db.search_workflow_runs.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_enabled_flag():
    svc = AdminOperationsService()
    assert svc.enabled is True
    assert "realtime_calls" in svc.capabilities()


@pytest.mark.asyncio
async def test_live_calls_snapshot():
    svc = AdminOperationsService()
    with (
        patch(
            "api.services.admin_operations.aggregators.calls.get_connection_manager"
        ) as mock_mgr,
        patch(
            "api.services.admin_operations.aggregators.calls.get_voice_pipeline_registry"
        ) as mock_reg,
        patch("api.services.admin_operations.aggregators.calls.db_client") as mock_db,
    ):
        mock_mgr.return_value.snapshot_sessions.return_value = [
            {"session_id": "abc", "active": True, "metadata": {"organization_id": 5}}
        ]
        mock_mgr.return_value.session_count.return_value = 1
        mock_reg.return_value.has_active.return_value = True
        mock_db.get_incomplete_workflow_runs = AsyncMock(return_value=[])

        result = await svc.live_calls(5)
    assert result["organization_id"] == 5
    assert result["active_audio_sessions"] == 1
    assert result["active_voice_pipelines"] == 1
