"""Structured logging for realtime voice observability."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Iterator

from loguru import logger

from api.services.realtime_observability.tracing import get_trace_context


def log_event(
    event: str,
    *,
    level: str = "info",
    session_id: str | None = None,
    **fields: Any,
) -> None:
    """Emit a structured JSON log line for realtime voice events."""
    payload = {
        "event": event,
        "ts": time.time(),
        "component": "realtime_voice",
        **get_trace_context(),
    }
    if session_id:
        payload["session_id"] = session_id
    payload.update({k: v for k, v in fields.items() if v is not None})
    message = json.dumps(payload, default=str, separators=(",", ":"))
    getattr(logger, level, logger.info)(message)


@contextmanager
def log_span(
    operation: str,
    *,
    session_id: str | None = None,
    **fields: Any,
) -> Iterator[dict[str, Any]]:
    """Log span start/end with duration_ms."""
    ctx: dict[str, Any] = dict(fields)
    start = time.monotonic()
    log_event(
        f"{operation}.start",
        session_id=session_id,
        operation=operation,
        **ctx,
    )
    try:
        yield ctx
    except Exception as exc:
        log_event(
            f"{operation}.error",
            level="error",
            session_id=session_id,
            operation=operation,
            error=str(exc),
            duration_ms=round((time.monotonic() - start) * 1000, 2),
            **ctx,
        )
        raise
    else:
        log_event(
            f"{operation}.end",
            session_id=session_id,
            operation=operation,
            duration_ms=round((time.monotonic() - start) * 1000, 2),
            **ctx,
        )
