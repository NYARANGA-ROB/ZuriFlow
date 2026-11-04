"""Tests for realtime audio protocol, queues, and connection manager."""

import asyncio
import time

import pytest

from api.services.realtime_audio.chunks import AudioChunkHandler
from api.services.realtime_audio.config import RealtimeAudioConfig
from api.services.realtime_audio.connection_manager import RealtimeAudioConnectionManager
from api.services.realtime_audio.errors import SessionExpiredError, SessionNotFoundError
from api.services.realtime_audio.protocol import (
    AudioChunkFrame,
    ControlType,
    decode_audio_chunk,
    decode_control,
    encode_audio_chunk,
    encode_control,
)
from api.services.realtime_audio.queues import BoundedAudioQueue


def test_binary_audio_roundtrip():
    pcm = b"\x00\x01" * 320
    frame = AudioChunkFrame(sequence=7, timestamp_ms=1234, pcm=pcm)
    wire = encode_audio_chunk(frame)
    decoded = decode_audio_chunk(wire)
    assert decoded.sequence == 7
    assert decoded.timestamp_ms == 1234
    assert decoded.pcm == pcm


def test_control_frames():
    hello = decode_control(
        encode_control(ControlType.HELLO, sample_rate=16000, channels=1)
    )
    assert hello["type"] == "hello"
    assert hello["sample_rate"] == 16000


@pytest.mark.asyncio
async def test_bounded_queue_drop_on_full():
    cfg = RealtimeAudioConfig(inbound_queue_maxsize=2, queue_put_timeout_s=0.01)
    q = BoundedAudioQueue("s1", "inbound", cfg.inbound_queue_maxsize, cfg.queue_put_timeout_s)
    chunk = AudioChunkFrame(sequence=0, timestamp_ms=0, pcm=b"\x00\x00" * 10)

    assert await q.put(chunk) is True
    assert await q.put(chunk) is True
    assert await q.put(chunk, drop_if_full=True) is False
    assert q.stats.dropped == 1
    await q.close()


@pytest.mark.asyncio
async def test_connection_manager_reconnect():
    cfg = RealtimeAudioConfig(reconnect_grace_s=1.0)
    mgr = RealtimeAudioConnectionManager(cfg)
    await mgr.start()

    session = await mgr.create_session(sample_rate=16000, client_id="c1")
    token = session.reconnect_token
    sid = session.session_id

    await mgr.release_session(sid, reason="test")
    resumed = await mgr.resume_session(
        session_id=sid,
        reconnect_token=token,
        last_ack_seq=3,
    )
    assert resumed.session_id == sid
    assert resumed.chunks.last_inbound_ack == 3

    await mgr.remove_session(sid, reason="done", graceful=True)
    await mgr.stop()


@pytest.mark.asyncio
async def test_reconnect_invalid_token():
    mgr = RealtimeAudioConnectionManager(RealtimeAudioConfig(reconnect_grace_s=5.0))
    session = await mgr.create_session()
    await mgr.release_session(session.session_id)
    with pytest.raises(SessionNotFoundError):
        await mgr.resume_session(
            session_id=session.session_id,
            reconnect_token="bad-token",
        )


def test_chunk_handler_validation():
    handler = AudioChunkHandler("s", sample_rate=16000, channels=1)
    chunk = handler.ingest_client_chunk(b"\x00\x00" * 160)
    assert chunk.sequence == 0
    out = handler.next_outbound_chunk(b"\x00\x00" * 160)
    assert out.sequence == 0
