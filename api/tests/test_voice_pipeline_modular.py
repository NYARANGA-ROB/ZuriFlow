"""Tests for modular voice pipeline example services."""

import asyncio

import pytest

from api.services.voice_pipeline.container import default_example_container
from api.services.voice_pipeline.orchestrator import ModularVoiceOrchestrator
from api.services.voice_pipeline.streaming.service import InMemoryMediaTransport
from api.services.voice_pipeline.types import AudioChunk, VoicePipelineConfig


@pytest.mark.asyncio
async def test_modular_echo_pipeline():
    from unittest.mock import AsyncMock, patch

    from api.services.voice_pipeline.telephony.service import RegistryTelephonySession

    container = default_example_container()
    config = VoicePipelineConfig(
        workflow_id=1,
        workflow_run_id=99,
        user_id=1,
        organization_id=1,
        provider_name="twilio",
        call_id="CA123",
        sample_rate=16000,
    )
    deps = container.build(config)
    transport = deps.transport
    assert isinstance(transport, InMemoryMediaTransport)

    orchestrator = ModularVoiceOrchestrator(deps)
    with patch.object(RegistryTelephonySession, "prepare", AsyncMock(return_value=None)):
        run_task = asyncio.create_task(orchestrator.run())

        pcm = b"\x00\x01" * 800
        for _ in range(8):
            await transport.inject_audio(
                AudioChunk(pcm=pcm, sample_rate=16000)
            )
        await asyncio.sleep(0.05)
        await orchestrator.stop()
        await asyncio.wait_for(run_task, timeout=5.0)

    snapshot = deps.metrics.snapshot()
    assert snapshot.workflow_run_id == 99
    assert snapshot.counters.get("call_started", 0) >= 1.0
