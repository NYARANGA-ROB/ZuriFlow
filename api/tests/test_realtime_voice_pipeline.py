"""Tests for interruption detection, cancellation, and conversation recovery."""

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.realtime_voice_pipeline.cancellation import InterruptionCancellationManager
from api.services.realtime_voice_pipeline.latency import PipelineLatencyTracker
from api.services.realtime_voice_pipeline.config import RealtimeVoicePipelineConfig
from api.services.realtime_voice_pipeline.handlers import TranscriptEventHandler
from api.services.realtime_voice_pipeline.interruption.detector import InterruptionDetector
from api.services.realtime_voice_pipeline.interruption.recovery import ConversationRecoveryManager
from api.services.realtime_voice_pipeline.interruption.tts_stop import TTSStopHandler
from api.services.realtime_voice_pipeline.interruption.vad import (
    VADConfig,
    VADEventKind,
    VoiceActivityDetector,
)
from api.services.realtime_voice_pipeline.queues import PipelineQueues
from api.services.realtime_voice_pipeline.types import PipelineControlEvent, PipelineControlKind
from api.services.voice_pipeline.types import LLMMessage, TranscriptEvent, TranscriptKind


def _loud_pcm(frames: int = 320, amplitude: int = 8000) -> bytes:
    return struct.pack(f"<{frames}h", *([amplitude] * frames))


def test_vad_detects_speech_start():
    vad = VoiceActivityDetector(config=VADConfig(energy_threshold=500.0, min_speech_frames=2))
    silent = b"\x00\x00" * 320
    events = []
    for _ in range(3):
        events.extend(vad.process(silent, sample_rate=16000))
    assert not any(e.kind == VADEventKind.SPEECH_START for e in events)

    events = []
    for _ in range(3):
        events.extend(vad.process(_loud_pcm(), sample_rate=16000))
    assert any(e.kind == VADEventKind.SPEECH_START for e in events)


def test_interruption_detector_vad_while_bot_active():
    cfg = RealtimeVoicePipelineConfig(session_id="d1")
    detector = InterruptionDetector(config=cfg, is_bot_active=lambda: True)
    from api.services.realtime_voice_pipeline.interruption.vad import VADEvent

    event = detector.on_vad(
        VADEvent(kind=VADEventKind.SPEECH_START, energy=900.0, timestamp_ms=0.0)
    )
    assert event is not None
    assert event.source.value == "vad"


def test_interruption_detector_ignores_vad_when_bot_idle():
    cfg = RealtimeVoicePipelineConfig(session_id="d2")
    detector = InterruptionDetector(config=cfg, is_bot_active=lambda: False)
    from api.services.realtime_voice_pipeline.interruption.vad import VADEvent

    event = detector.on_vad(
        VADEvent(kind=VADEventKind.SPEECH_START, energy=900.0, timestamp_ms=0.0)
    )
    assert event is None


def test_conversation_recovery_discards_partial_assistant():
    recovery = ConversationRecoveryManager()
    recovery.append_user("What's the weather?")
    recovery.begin_assistant_turn()
    recovery.append_assistant_delta("The weather today is")
    recovery.on_interruption(partial_assistant="The weather today is")
    recovery.resume_after_interrupt()
    recovery.append_user("Actually, what about tomorrow?")

    messages = recovery.messages_for_generation()
    assert messages == [
        LLMMessage(role="user", content="What's the weather?"),
        LLMMessage(role="user", content="Actually, what about tomorrow?"),
    ]


@pytest.mark.asyncio
async def test_cancellation_ordered_interrupt():
    llm = AsyncMock()
    stt = AsyncMock()
    queues = PipelineQueues(RealtimeVoicePipelineConfig(session_id="c1"))
    tts = MagicMock()
    tts.interrupt = AsyncMock()
    tts.end_synthesis = AsyncMock()
    tts.release_generation_sink = MagicMock()

    from api.services.voice_pipeline.text_to_speech.streaming_adapter import StreamingTTSBridge

    bridge = MagicMock(spec=StreamingTTSBridge)
    bridge.interrupt = AsyncMock()
    bridge.end_synthesis = AsyncMock()
    bridge.release_generation_sink = MagicMock()

    tts_stop = TTSStopHandler(tts=bridge, queues=queues)
    recovery = ConversationRecoveryManager()
    mgr = InterruptionCancellationManager(
        llm=llm, stt=stt, tts_stop=tts_stop, recovery=recovery, queues=queues
    )
    mgr.mark_llm_active()
    mgr.mark_bot_speaking(generation_id="tts-1")
    recovery.begin_assistant_turn()
    recovery.append_assistant_delta("partial")

    from api.services.realtime_voice_pipeline.interruption.detector import InterruptionEvent, InterruptionSource

    result = await mgr.handle_interruption(
        InterruptionEvent(source=InterruptionSource.VAD, reason="test")
    )
    assert result["cancelled"] is True
    bridge.interrupt.assert_awaited()
    llm.interrupt.assert_awaited_once()
    stt.interrupt.assert_awaited_once()
    assert mgr.should_barge_in is False
    assert recovery.partial_assistant_text() == ""


@pytest.mark.asyncio
async def test_pipeline_queues_flush_outbound():
    cfg = RealtimeVoicePipelineConfig(session_id="q1")
    queues = PipelineQueues(cfg)
    from api.services.voice_pipeline.types import AudioChunk

    await queues.outbound_audio.put(AudioChunk(pcm=b"\x00", sample_rate=16000))
    await queues.outbound_audio.put(AudioChunk(pcm=b"\x01", sample_rate=16000))
    assert queues.flush_outbound() == 2
    assert queues.outbound_audio.empty()


@pytest.mark.asyncio
async def test_transcript_handler_triggers_turn_on_final():
    cfg = RealtimeVoicePipelineConfig(session_id="t1")
    queues = PipelineQueues(cfg)
    stop = asyncio.Event()
    cancellation = InterruptionCancellationManager()
    recovery = ConversationRecoveryManager()
    detector = InterruptionDetector(config=cfg, is_bot_active=cancellation.should_barge_in)
    handler = TranscriptEventHandler(
        queues=queues,
        detector=detector,
        cancellation=cancellation,
        recovery=recovery,
        latency=PipelineLatencyTracker(workflow_run_id=0),
        config=cfg,
        stop=stop,
    )

    task = asyncio.create_task(handler.run())
    await queues.transcript_events.put(
        TranscriptEvent(text="hello world", kind=TranscriptKind.FINAL)
    )

    await asyncio.wait_for(handler.wait_for_turn(), timeout=1.0)
    assert recovery.messages_for_generation() == [
        LLMMessage(role="user", content="hello world")
    ]

    stop.set()
    await queues.transcript_events.put(None)
    await task


@pytest.mark.asyncio
async def test_transcript_handler_barge_in_on_partial():
    cfg = RealtimeVoicePipelineConfig(session_id="t2", min_partial_chars_for_barge_in=2)
    queues = PipelineQueues(cfg)
    stop = asyncio.Event()
    llm = AsyncMock()
    stt = AsyncMock()
    bridge = MagicMock()
    bridge.interrupt = AsyncMock()
    bridge.end_synthesis = AsyncMock()
    bridge.release_generation_sink = MagicMock()
    tts_stop = TTSStopHandler(tts=bridge, queues=queues)
    cancellation = InterruptionCancellationManager(
        llm=llm, stt=stt, tts_stop=tts_stop, queues=queues
    )
    cancellation.mark_bot_speaking()
    detector = InterruptionDetector(
        config=cfg, is_bot_active=lambda: cancellation.should_barge_in
    )

    handler = TranscriptEventHandler(
        queues=queues,
        detector=detector,
        cancellation=cancellation,
        recovery=ConversationRecoveryManager(),
        latency=PipelineLatencyTracker(workflow_run_id=0),
        config=cfg,
        stop=stop,
    )
    task = asyncio.create_task(handler.run())
    await queues.transcript_events.put(
        TranscriptEvent(text="hey", kind=TranscriptKind.PARTIAL)
    )
    await asyncio.sleep(0.05)

    bridge.interrupt.assert_awaited()
    stop.set()
    await queues.transcript_events.put(None)
    await task


@pytest.mark.asyncio
async def test_control_queue_interrupt():
    cfg = RealtimeVoicePipelineConfig(session_id="c1")
    queues = PipelineQueues(cfg)
    stop = asyncio.Event()
    llm = AsyncMock()
    cancellation = InterruptionCancellationManager(llm=llm)
    cancellation.mark_llm_active()
    detector = InterruptionDetector(config=cfg, is_bot_active=cancellation.should_barge_in)

    from api.services.realtime_voice_pipeline.handlers import ControlEventHandler

    handler = ControlEventHandler(
        queues=queues, cancellation=cancellation, detector=detector, stop=stop
    )
    task = asyncio.create_task(handler.run())
    await queues.put_control(
        PipelineControlEvent(kind=PipelineControlKind.INTERRUPT, reason="test")
    )
    await asyncio.sleep(0.05)
    llm.interrupt.assert_awaited()

    await queues.control.put(None)
    await task


def test_latency_tracker_turn_deltas():
    tracker = PipelineLatencyTracker(workflow_run_id=1)
    tracker.begin_turn()
    tracker.mark("stt_final")
    tracker.mark("llm_first_token")
    tracker.mark("tts_first_byte")
    deltas = tracker.record_turn_complete()
    assert deltas["turn_e2e_ms"] is not None
    assert deltas["stt_to_llm_start_ms"] is not None


def test_put_nowait_drop():
    cfg = RealtimeVoicePipelineConfig(session_id="drop", inbound_audio_maxsize=2)
    queues = PipelineQueues(cfg)
    from api.services.voice_pipeline.types import AudioChunk

    chunk = AudioChunk(pcm=b"\x00", sample_rate=16000)
    assert queues.put_inbound(chunk)
    assert queues.put_inbound(chunk)
    assert queues.put_inbound(chunk)
    assert queues.inbound_audio.qsize() == 2
