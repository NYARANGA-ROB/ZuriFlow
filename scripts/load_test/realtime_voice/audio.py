"""Synthetic PCM audio generation for load tests."""

from __future__ import annotations

import math
import struct
from typing import Iterator


def generate_pcm_chunk(
    *,
    sequence: int,
    sample_rate: int,
    channels: int,
    chunk_ms: int,
    pattern: str = "tone",
) -> bytes:
    """Generate one PCM int16 chunk simulating caller audio."""
    samples_per_channel = int(sample_rate * chunk_ms / 1000)
    total_samples = samples_per_channel * channels
    if pattern == "silence":
        return b"\x00\x00" * total_samples

    frames: list[int] = []
    for i in range(samples_per_channel):
        t = (sequence * samples_per_channel + i) / sample_rate
        if pattern == "noise":
            # Deterministic pseudo-noise from index (fast, no random import)
            val = ((sequence * 997 + i * 13) % 2000) - 1000
        elif pattern == "alternating":
            val = 6000 if (sequence + i // 100) % 2 == 0 else -6000
        else:  # tone — simulates speech energy for VAD/STT paths
            freq = 220.0 + (sequence % 5) * 40.0
            val = int(5000 * math.sin(2 * math.pi * freq * t))

        sample = max(-32768, min(32767, val))
        for _ in range(channels):
            frames.append(sample)

    return struct.pack(f"<{len(frames)}h", *frames)


def stream_chunks(
    *,
    sample_rate: int,
    channels: int,
    chunk_ms: int,
    pattern: str,
    count: int,
    start_seq: int = 0,
) -> Iterator[bytes]:
    for seq in range(start_seq, start_seq + count):
        yield generate_pcm_chunk(
            sequence=seq,
            sample_rate=sample_rate,
            channels=channels,
            chunk_ms=chunk_ms,
            pattern=pattern,
        )
