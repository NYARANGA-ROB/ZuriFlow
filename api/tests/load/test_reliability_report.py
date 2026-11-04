"""Reliability report generation tests."""

from __future__ import annotations

import json

import pytest

from api.services.reliability_testing.reliability_report import ReliabilityReportWriter
from api.services.reliability_testing.runner import WorkflowReliabilityRunner
from api.services.reliability_testing.types import ReliabilityReport, ScenarioResult, StressScenario


@pytest.mark.reliability
def test_reliability_report_json_structure():
    report = ReliabilityReport(config={"test": True})
    scenario = ScenarioResult(scenario=StressScenario.CONCURRENT_CALLS)
    scenario.total = 10
    scenario.succeeded = 9
    scenario.failed = 1
    scenario.finish()
    report.add(scenario)
    report.finish()

    data = report.to_dict()
    assert data["overall_success_rate"] == 0.9
    assert len(data["scenarios"]) == 1


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_reliability_report_write_files(tmp_path):
    runner = WorkflowReliabilityRunner(
        concurrent_calls=5,
        stk_spike_size=5,
        whatsapp_spike_size=5,
        interruption_burst=5,
        retry_operations=5,
        report_dir=str(tmp_path),
        skip_live_websocket=True,
    )
    report, json_path, html_path = await runner.run_and_write()
    assert json_path.endswith(".json")
    assert html_path.endswith(".html")
    payload = json.loads(open(json_path, encoding="utf-8").read())
    assert payload["overall_success_rate"] >= 0.0
    assert len(payload["scenarios"]) == 6
