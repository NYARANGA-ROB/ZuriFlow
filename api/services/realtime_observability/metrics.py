"""Prometheus metric definitions for the realtime voice system."""

from __future__ import annotations

from api.services.realtime_observability.prometheus_registry import (
    Counter,
    Gauge,
    Histogram,
    PrometheusRegistry,
)

REGISTRY = PrometheusRegistry()

# WebSocket
WS_ROUNDTRIP_MS = Histogram(
    "dograh_realtime_ws_roundtrip_ms",
    "WebSocket ping/pong round-trip latency in milliseconds",
    buckets=(5, 10, 25, 50, 100, 200, 500, 1000),
    registry=REGISTRY,
)
WS_CONNECT_MS = Histogram(
    "dograh_realtime_ws_connect_ms",
    "Time from WebSocket accept to hello_ack in milliseconds",
    buckets=(10, 25, 50, 80, 150, 250, 500, 1000),
    registry=REGISTRY,
)
WS_CONNECTIONS_TOTAL = Counter(
    "dograh_realtime_ws_connections_total",
    "Total WebSocket connections opened",
    labelnames=("endpoint",),
    registry=REGISTRY,
)
WS_DISCONNECTS_TOTAL = Counter(
    "dograh_realtime_ws_disconnects_total",
    "Total WebSocket disconnects",
    labelnames=("endpoint", "reason"),
    registry=REGISTRY,
)

# Pipeline stages
STT_RESPONSE_MS = Histogram(
    "dograh_realtime_stt_response_ms",
    "STT final transcript latency from turn start in milliseconds",
    buckets=(50, 100, 200, 400, 800, 1600),
    registry=REGISTRY,
)
LLM_FIRST_TOKEN_MS = Histogram(
    "dograh_realtime_llm_first_token_ms",
    "LLM time-to-first-token from turn start in milliseconds",
    buckets=(50, 100, 200, 400, 800, 1600, 3200),
    registry=REGISTRY,
)
LLM_TOTAL_MS = Histogram(
    "dograh_realtime_llm_total_ms",
    "Total LLM generation time in milliseconds",
    buckets=(100, 250, 500, 1000, 2000, 5000),
    registry=REGISTRY,
)
TTS_FIRST_BYTE_MS = Histogram(
    "dograh_realtime_tts_first_byte_ms",
    "TTS time-to-first-audio-byte from turn start in milliseconds",
    buckets=(50, 100, 200, 400, 800, 1600),
    registry=REGISTRY,
)
TTS_GENERATION_MS = Histogram(
    "dograh_realtime_tts_generation_ms",
    "Total TTS synthesis duration in milliseconds",
    buckets=(100, 250, 500, 1000, 2000, 5000),
    registry=REGISTRY,
)
NORMALIZE_MS = Histogram(
    "dograh_realtime_normalize_ms",
    "Transcript normalization duration in milliseconds",
    buckets=(1, 5, 10, 25, 50, 100, 250),
    registry=REGISTRY,
)
INTENT_MS = Histogram(
    "dograh_realtime_intent_ms",
    "Intent classification duration in milliseconds",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500),
    registry=REGISTRY,
)
WORKFLOW_STAGE_MS = Histogram(
    "dograh_realtime_workflow_ms",
    "Workflow node / tool-registration work in milliseconds",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500),
    registry=REGISTRY,
)
TOOL_CALL_MS = Histogram(
    "dograh_realtime_tool_call_ms",
    "Privileged tool invocation duration in milliseconds",
    buckets=(50, 100, 250, 500, 1000, 2000, 5000),
    registry=REGISTRY,
)
CALL_STARTUP_MS = Histogram(
    "dograh_realtime_call_startup_ms",
    "Time from session accept to pipeline ready in milliseconds",
    buckets=(100, 250, 500, 1000, 2000, 4000),
    registry=REGISTRY,
)
FIRST_RESPONSE_MS = Histogram(
    "dograh_realtime_first_response_ms",
    "First bot audio after user final transcript in milliseconds",
    buckets=(200, 400, 600, 800, 1000, 1500, 2000, 3000),
    registry=REGISTRY,
)
E2E_LATENCY_MS = Histogram(
    "dograh_realtime_e2e_latency_ms",
    "End-to-end user-to-bot audio latency in milliseconds",
    buckets=(200, 400, 600, 800, 1000, 1500, 2000, 3000),
    registry=REGISTRY,
)

# Operational
INTERRUPTIONS_TOTAL = Counter(
    "dograh_realtime_interruptions_total",
    "Caller interruption (barge-in) events",
    labelnames=("source",),
    registry=REGISTRY,
)
RECONNECTS_TOTAL = Counter(
    "dograh_realtime_reconnects_total",
    "WebSocket session reconnects within grace period",
    labelnames=("endpoint",),
    registry=REGISTRY,
)
ACTIVE_SESSIONS = Gauge(
    "dograh_realtime_active_sessions",
    "Currently active realtime audio/voice sessions",
    labelnames=("endpoint",),
    registry=REGISTRY,
)
QUEUE_DROPS_TOTAL = Counter(
    "dograh_realtime_queue_drops_total",
    "Audio/event queue drops due to backpressure",
    labelnames=("queue",),
    registry=REGISTRY,
)
TURNS_TOTAL = Counter(
    "dograh_realtime_turns_total",
    "Completed conversation turns",
    labelnames=("status",),
    registry=REGISTRY,
)
EXTERNAL_API_CIRCUIT_OPEN = Gauge(
    "dograh_external_api_circuit_open",
    "1 when external API circuit breaker is open",
    labelnames=("service",),
    registry=REGISTRY,
)
