"""Wire protocol for realtime audio WebSocket sessions.

Control plane: JSON text frames.
Data plane: binary frames with a fixed 18-byte header + PCM payload.

Binary header (little-endian):
  version     uint8   = 1
  flags       uint8   = 0
  sequence    uint32
  timestamp   uint64  milliseconds since session start
  payload_len uint32
  payload     int16 PCM mono/stereo
"""

from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from api.services.realtime_audio.errors import ProtocolError

BINARY_HEADER = struct.Struct("<BBIQI")
BINARY_VERSION = 1
BINARY_HEADER_SIZE = BINARY_HEADER.size  # 18


class ControlType(str, Enum):
    HELLO = "hello"
    HELLO_ACK = "hello_ack"
    RECONNECT = "reconnect"
    PING = "ping"
    PONG = "pong"
    DISCONNECT = "disconnect"
    ERROR = "error"
    AUDIO_ACK = "audio_ack"


@dataclass(frozen=True)
class AudioChunkFrame:
    sequence: int
    timestamp_ms: int
    pcm: bytes

    @property
    def nbytes(self) -> int:
        return len(self.pcm)


def encode_audio_chunk(chunk: AudioChunkFrame) -> bytes:
    if len(chunk.pcm) > 2**32 - 1:
        raise ProtocolError("audio chunk exceeds maximum size")
    return BINARY_HEADER.pack(
        BINARY_VERSION,
        0,
        chunk.sequence & 0xFFFFFFFF,
        chunk.timestamp_ms & 0xFFFFFFFFFFFFFFFF,
        len(chunk.pcm),
    ) + chunk.pcm


def decode_audio_chunk(data: bytes) -> AudioChunkFrame:
    if len(data) < BINARY_HEADER_SIZE:
        raise ProtocolError("binary frame too short")
    version, _flags, seq, ts_ms, payload_len = BINARY_HEADER.unpack_from(data)
    if version != BINARY_VERSION:
        raise ProtocolError(f"unsupported binary version: {version}")
    end = BINARY_HEADER_SIZE + payload_len
    if len(data) < end:
        raise ProtocolError("truncated binary audio payload")
    pcm = data[BINARY_HEADER_SIZE:end]
    return AudioChunkFrame(sequence=seq, timestamp_ms=ts_ms, pcm=pcm)


def encode_control(message_type: ControlType, **fields: Any) -> str:
    payload = {"type": message_type.value, **fields}
    return json.dumps(payload, separators=(",", ":"))


def decode_control(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"invalid JSON control frame: {e}") from e
    if not isinstance(data, dict) or "type" not in data:
        raise ProtocolError("control frame must be a JSON object with 'type'")
    return data


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)
