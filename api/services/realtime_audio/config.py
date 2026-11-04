"""Tunables for the realtime audio WebSocket server."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealtimeAudioConfig:
    """Bounded-resource defaults tuned for low memory and telephony-scale sessions."""

    # Audio
    default_sample_rate: int = 16000
    default_channels: int = 1
    max_chunk_bytes: int = 8192  # ~256 ms @ 16 kHz mono 16-bit PCM
    bytes_per_sample: int = 2

    # Queues — bounded to cap memory per connection (~32 * 8 KB ≈ 256 KB/side)
    inbound_queue_maxsize: int = 32
    outbound_queue_maxsize: int = 32
    queue_put_timeout_s: float = 0.05

    # Heartbeat
    heartbeat_interval_s: float = 5.0
    heartbeat_timeout_s: float = 15.0
    server_ping_interval_s: float = 5.0

    # Reconnect grace — session state kept after disconnect
    reconnect_grace_s: float = 30.0
    max_sessions: int = 10_000

    # WebSocket
    ws_max_message_size: int = 16_384
    close_timeout_s: float = 2.0


DEFAULT_CONFIG = RealtimeAudioConfig()
