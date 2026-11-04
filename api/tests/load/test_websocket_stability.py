"""WebSocket stability and reconnect reliability tests."""

from __future__ import annotations

import os

import pytest

from api.services.reliability_testing.websocket_stability import WebSocketStabilityProbe


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_websocket_stability_simulated():
    probe = WebSocketStabilityProbe(
        reconnect_attempts=4,
        session_duration_s=2.0,
        ping_interval_s=0.3,
    )
    result = await probe.run_simulated()
    assert result.total >= 4
    assert result.metadata["reconnects"] == 4


@pytest.mark.live_load
@pytest.mark.asyncio
async def test_websocket_stability_live(live_ws_url):
    if not live_ws_url:
        pytest.skip("Set LOAD_TEST_WS_URL for live WebSocket probe")
    probe = WebSocketStabilityProbe(reconnect_attempts=1, session_duration_s=5.0)
    result = await probe.run_live(live_ws_url)
    assert result.success_rate >= 0.5


@pytest.mark.reliability
@pytest.mark.asyncio
async def test_realtime_audio_queue_under_burst():
    """Bounded queue should drop rather than block under burst."""
    from api.services.realtime_audio.config import RealtimeAudioConfig
    from api.services.realtime_audio.protocol import AudioChunkFrame
    from api.services.realtime_audio.queues import BoundedAudioQueue

    cfg = RealtimeAudioConfig(inbound_queue_maxsize=4)
    q = BoundedAudioQueue("s", "inbound", cfg.inbound_queue_maxsize, 0.0)
    chunk = AudioChunkFrame(sequence=0, timestamp_ms=0, pcm=b"\x00" * 64)
    accepted = 0
    dropped = 0
    for _ in range(20):
        if await q.put(chunk, drop_if_full=True):
            accepted += 1
        else:
            dropped += 1
    await q.close()
    assert dropped > 0
    assert accepted <= 4
