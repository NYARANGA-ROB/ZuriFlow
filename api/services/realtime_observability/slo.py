"""Measurable latency SLOs. These are engineering targets, not contractual SLAs."""

from __future__ import annotations

from api.services.realtime_observability.percentiles import snapshot

# Milliseconds. Conservative production-grade conversational targets.
TARGETS_MS = {
    "websocket_connect": {"p50": 80, "p95": 250, "p99": 500},
    "call_startup": {"p50": 800, "p95": 2000, "p99": 3500},
    "stt": {"p50": 250, "p95": 600, "p99": 1200},
    "normalize": {"p50": 15, "p95": 40, "p99": 80},
    "intent": {"p50": 25, "p95": 80, "p99": 150},
    "workflow": {"p50": 20, "p95": 80, "p99": 150},
    "llm_first_token": {"p50": 400, "p95": 900, "p99": 1600},
    "tool_call": {"p50": 300, "p95": 1200, "p99": 2500},
    "tts_first_byte": {"p50": 200, "p95": 500, "p99": 900},
    "first_response": {"p50": 900, "p95": 1800, "p99": 2800},
    "turn_e2e": {"p50": 1200, "p95": 2200, "p99": 3500},
}

STAGE_ALIASES = {
    "stt_final": "stt",
    "turn_e2e_ms": "turn_e2e",
    "llm_first_token": "llm_first_token",
    "tts_first_byte": "tts_first_byte",
}


def evaluate_slos() -> dict:
    observed = snapshot()
    results = []
    for stage, targets in TARGETS_MS.items():
        sample = observed.get(stage) or observed.get(
            next((k for k, v in STAGE_ALIASES.items() if v == stage), stage),
            {},
        )
        row = {
            "stage": stage,
            "targets_ms": targets,
            "observed": sample,
            "meets_p95": None,
        }
        p95 = sample.get("p95") if isinstance(sample, dict) else None
        if p95 is not None:
            row["meets_p95"] = p95 <= targets["p95"]
        results.append(row)
    return {
        "targets": TARGETS_MS,
        "stages": results,
        "note": (
            "Targets are internal engineering goals for conversational voice. "
            "They are not availability SLAs or regulatory claims."
        ),
    }
