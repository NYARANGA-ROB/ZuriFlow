"""Tests for streaming TTS buffering, cancellation, and playback."""

import asyncio

import pytest

from api.services.streaming_tts.buffering import AudioBufferService
from api.services.streaming_tts.cancellation import CancellationRegistry, SynthesisCancellationToken
from api.services.streaming_tts.config import StreamingTTSConfig
from api.services.streaming_tts.playback import StreamingPlaybackHandler
from api.services.streaming_tts.types import TTSStreamEvent, TTSStreamKind


@pytest.mark.asyncio
async def test_audio_buffer_preroll():
    cfg = StreamingTTSConfig(min_playback_buffer_ms=20, sample_rate=16000)
    buf = AudioBufferService("test", cfg)
    chunk_bytes = b"\x00\x00" * 200  # 400 bytes

    await buf.push_event(
        TTSStreamEvent(
            kind=TTSStreamKind.AUDIO_CHUNK,
            audio=chunk_bytes,
            generation_id="g1",
        )
    )
    # Below min preroll — nothing released yet
    assert buf._queue.empty()

    # Add enough to exceed min preroll (~640 bytes for 20ms @ 16kHz)
    for _ in range(2):
        await buf.push_event(
            TTSStreamEvent(
                kind=TTSStreamKind.AUDIO_CHUNK,
                audio=chunk_bytes,
                generation_id="g1",
            )
        )

    await buf.flush()
    assert not buf._queue.empty()
    await buf.close()


def test_cancellation_token():
    reg = CancellationRegistry()
    token = reg.create("gen-1")
    assert not token.is_cancelled
    reg.cancel("gen-1")
    assert token.is_cancelled


@pytest.mark.asyncio
async def test_playback_interrupt_clears_buffer():
    cfg = StreamingTTSConfig(min_playback_buffer_ms=1000, sample_rate=16000)
    buf = AudioBufferService("sess", cfg)
    played: list[bytes] = []

    async def on_chunk(chunk):
        played.append(chunk.pcm)

    handler = StreamingPlaybackHandler(
        session_id="sess",
        buffer=buf,
        on_chunk=on_chunk,
    )
    await handler.start()

    await handler.handle_event(
        TTSStreamEvent(kind=TTSStreamKind.SYNTHESIS_START, generation_id="g1")
    )
    await handler.handle_event(
        TTSStreamEvent(
            kind=TTSStreamKind.AUDIO_CHUNK,
            generation_id="g1",
            audio=b"\x01\x00" * 100,
            sample_rate=16000,
        )
    )
    await handler.interrupt("g1")
    assert buf._preroll == [] or buf._queue.empty()

    await handler.stop()
