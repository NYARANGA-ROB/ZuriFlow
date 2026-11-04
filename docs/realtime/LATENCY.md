# Realtime conversational latency

Engineering targets for ZuriFlow voice. These are **not** contractual SLAs and
do **not** claim regulatory compliance.

## Pipeline

```
STT → normalize → intent → workflow → LLM → tool calls → TTS
```

Streaming is enabled on the dedicated WebSocket path (`/realtime-voice/ws`):
streaming STT (including interim transcripts), streaming LLM tokens, streaming
TTS, and barge-in that stops TTS, preserves conversation state, and flushes
outbound audio before processing the new utterance.

Telephony/WebRTC uses Pipecat with the same stage histograms via
`TurnLatencyProcessor`. Recordings, analytics, CRM, receipts, and learning stay
on ARQ (`PROCESS_WORKFLOW_COMPLETION`) after hangup.

## Targets (milliseconds)

| Metric | p50 | p95 | p99 |
| --- | --- | --- | --- |
| WebSocket connect | 80 | 250 | 500 |
| Call startup | 800 | 2000 | 3500 |
| STT (final) | 250 | 600 | 1200 |
| Normalize | 15 | 40 | 80 |
| Intent | 25 | 80 | 150 |
| Workflow | 20 | 80 | 150 |
| LLM first token | 400 | 900 | 1600 |
| Tool call | 300 | 1200 | 2500 |
| TTS first byte | 200 | 500 | 900 |
| First bot response | 900 | 1800 | 2800 |
| Average turn (e2e) | 1200 | 2200 | 3500 |

Live p50/p95/p99: `GET /api/v1/realtime-observability/slo`  
Prometheus: `GET /api/v1/realtime-observability/metrics`

## Correlation

Every call binds `call_id` / `trace_id` / `session_id` / `organization_id` /
`workflow_run_id` (contextvars + optional `X-Call-Id`). Workers still key off
`workflow_run_id`.

## Caching (tenant-safe)

Redis keys are `voice_rt:{organization_id}:{kind}:{hash}`. Phone numbers,
transcripts, recordings, secrets, and payment fields are refused. Cost-cache
answers remain org-scoped as before.

Safe cache kinds: workflow correlation (`corr`), Kenya session counters
(`kenya_sess`, no transcripts), static prompt merge (in-process LRU),
configuration. WebSocket connects are rate-limited per organization.

## Redis / ARQ

Redis holds ephemeral session counters, connect rate limits, and call
correlation for workers. ARQ `PROCESS_WORKFLOW_COMPLETION` uploads recordings,
runs analytics/CRM/integrations, and billing after hangup — never on the audio
loop.

## Tracing

`call_id` / `trace_id` bind Browser → API → Pipecat → STT/LLM/TTS → tools →
Postgres → ARQ workers (`X-Call-Id`). Worker completion logs replay the same
`call_id` from the org-scoped Redis correlation record.

## Benchmark

Existing load test: `python -m scripts.load_test.realtime_voice`  
Unit percentiles: `api/tests/test_realtime_latency_hardening.py`

Capture Prometheus histograms before a change, run the load test, then compare
`dograh_realtime_*_ms` p95 and `/realtime-observability/slo`.
