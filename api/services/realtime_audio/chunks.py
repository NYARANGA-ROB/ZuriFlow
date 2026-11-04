"""Audio chunk validation, sequencing, and session-scoped handlers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from api.services.realtime_audio.config import RealtimeAudioConfig, DEFAULT_CONFIG
from api.services.realtime_audio.errors import ProtocolError
from api.services.realtime_audio.protocol import AudioChunkFrame, monotonic_ms


@dataclass
class AudioChunkHandler:
    """Per-session sequencer and validator for PCM chunks."""

    session_id: str
    sample_rate: int
    channels: int
    config: RealtimeAudioConfig = DEFAULT_CONFIG
    _inbound_seq: int = field(default=0, init=False)
    _outbound_seq: int = field(default=0, init=False)
    _last_inbound_ack: int = field(default=-1, init=False)
    _started_mono: float = field(default_factory=time.monotonic, init=False)

    def validate_pcm(self, pcm: bytes) -> None:
        if not pcm:
            raise ProtocolError("empty audio payload")
        if len(pcm) > self.config.max_chunk_bytes:
            raise ProtocolError(
                f"chunk size {len(pcm)} exceeds max {self.config.max_chunk_bytes}"
            )
        if len(pcm) % self.config.bytes_per_sample != 0:
            raise ProtocolError("PCM length must align to sample width")
        frame_samples = len(pcm) // (self.config.bytes_per_sample * self.channels)
        if frame_samples == 0:
            raise ProtocolError("chunk contains no audio samples")

    def ingest_client_chunk(self, pcm: bytes, *, client_seq: int | None = None) -> AudioChunkFrame:
        self.validate_pcm(pcm)
        if client_seq is not None and client_seq <= self._last_inbound_ack:
            raise ProtocolError(f"stale inbound sequence {client_seq}")
        seq = client_seq if client_seq is not None else self._inbound_seq
        self._inbound_seq = max(self._inbound_seq, seq + 1)
        ts = monotonic_ms() - int((time.monotonic() - self._started_mono) * 1000)
        return AudioChunkFrame(sequence=seq, timestamp_ms=ts, pcm=pcm)

    def next_outbound_chunk(self, pcm: bytes) -> AudioChunkFrame:
        self.validate_pcm(pcm)
        seq = self._outbound_seq
        self._outbound_seq += 1
        ts = monotonic_ms() - int((time.monotonic() - self._started_mono) * 1000)
        return AudioChunkFrame(sequence=seq, timestamp_ms=ts, pcm=pcm)

    def ack_inbound(self, seq: int) -> None:
        if seq < self._last_inbound_ack:
            return
        self._last_inbound_ack = seq

    def resume_from(self, last_ack_seq: int) -> None:
        """Restore sequencer state after reconnect."""
        self._last_inbound_ack = last_ack_seq
        self._inbound_seq = max(self._inbound_seq, last_ack_seq + 1)

    @property
    def last_inbound_ack(self) -> int:
        return self._last_inbound_ack

    @property
    def outbound_seq(self) -> int:
        return self._outbound_seq
