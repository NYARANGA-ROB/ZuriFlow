"""Load test configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EndpointKind(str, Enum):
    REALTIME_AUDIO = "realtime_audio"
    REALTIME_VOICE = "realtime_voice"


@dataclass
class LoadTestConfig:
    """Tunables for realtime voice load tests."""

    base_url: str = "ws://localhost:8000"
    endpoint: EndpointKind = EndpointKind.REALTIME_AUDIO
    api_prefix: str = "/api/v1"

    # Concurrency
    concurrent_callers: int = 10
    ramp_up_s: float = 5.0
    duration_s: float = 30.0
    spawn_interval_s: float = 0.0  # 0 = auto from ramp_up / callers

    # Audio simulation
    sample_rate: int = 16000
    channels: int = 1
    chunk_ms: int = 20
    speech_pattern: str = "tone"  # tone | noise | silence | alternating

    # Stress
    send_audio: bool = True
    drain_outbound: bool = True
    heartbeat_interval_s: float = 5.0
    connect_timeout_s: float = 10.0
    per_caller_timeout_s: float = 120.0

    # Memory leak detection
    memory_check_interval_s: float = 10.0
    memory_growth_threshold_mb: float = 50.0

    # Reporting
    report_dir: str = "load_test_reports"
    report_prefix: str = "realtime_voice"

    # Voice endpoint metadata (optional)
    workflow_run_id: int = 0
    system_prompt: str = "Load test caller"

    def websocket_url(self) -> str:
        path = {
            EndpointKind.REALTIME_AUDIO: f"{self.api_prefix}/realtime-audio/ws",
            EndpointKind.REALTIME_VOICE: f"{self.api_prefix}/realtime-voice/ws",
        }[self.endpoint]
        base = self.base_url.rstrip("/")
        return f"{base}{path}"

    def hello_metadata(self) -> dict:
        if self.endpoint != EndpointKind.REALTIME_VOICE:
            return {}
        return {
            "workflow_run_id": self.workflow_run_id,
            "system_prompt": self.system_prompt,
        }

    def chunk_bytes(self) -> int:
        samples = int(self.sample_rate * self.chunk_ms / 1000) * self.channels
        return samples * 2  # int16
