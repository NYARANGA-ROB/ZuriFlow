from __future__ import annotations

import os
from dataclasses import dataclass, field

from api.services.reliability_testing.failure_injector import RetryRecoverySimulator
from api.services.reliability_testing.reliability_report import ReliabilityReportWriter
from api.services.reliability_testing.spike_simulators import STKPushSpikeSimulator, WhatsAppSpikeSimulator
from api.services.reliability_testing.types import ReliabilityReport
from api.services.reliability_testing.voice_simulator import (
    InterruptionBurstSimulator,
    VoiceCallSessionSimulator,
)
from api.services.reliability_testing.websocket_stability import WebSocketStabilityProbe


@dataclass
class WorkflowReliabilityRunner:
    """Orchestrate full AI call workflow reliability scenarios."""

    concurrent_calls: int = 20
    stk_spike_size: int = 50
    whatsapp_spike_size: int = 80
    interruption_burst: int = 30
    retry_operations: int = 40
    websocket_reconnects: int = 3
    report_dir: str = "reliability_reports"
    live_websocket_url: str | None = None
    skip_live_websocket: bool = True

    _report: ReliabilityReport = field(default_factory=ReliabilityReport)

    async def run_all(self) -> ReliabilityReport:
        self._report = ReliabilityReport(
            config={
                "concurrent_calls": self.concurrent_calls,
                "stk_spike_size": self.stk_spike_size,
                "whatsapp_spike_size": self.whatsapp_spike_size,
            }
        )

        self._report.add(await VoiceCallSessionSimulator(concurrent_sessions=self.concurrent_calls).run())
        self._report.add(await STKPushSpikeSimulator(spike_size=self.stk_spike_size).run())
        self._report.add(await WhatsAppSpikeSimulator(spike_size=self.whatsapp_spike_size).run())
        self._report.add(await InterruptionBurstSimulator(burst_count=self.interruption_burst).run())
        self._report.add(await RetryRecoverySimulator(operations=self.retry_operations).run())

        ws_url = self.live_websocket_url or os.getenv("LOAD_TEST_WS_URL")
        if ws_url and not self.skip_live_websocket:
            self._report.add(
                await WebSocketStabilityProbe(
                    reconnect_attempts=self.websocket_reconnects
                ).run_live(ws_url)
            )
        else:
            self._report.add(
                await WebSocketStabilityProbe(
                    reconnect_attempts=self.websocket_reconnects
                ).run_simulated()
            )

        self._report.finish()
        return self._report

    async def run_and_write(self) -> tuple[ReliabilityReport, str, str]:
        report = await self.run_all()
        writer = ReliabilityReportWriter(report, report_dir=self.report_dir)
        json_path, html_path = writer.write()
        writer.print_console()
        return report, str(json_path), str(html_path)
