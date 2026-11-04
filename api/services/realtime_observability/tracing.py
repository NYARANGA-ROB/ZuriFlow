"""Distributed tracing hooks for realtime voice sessions."""

from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("session_id", default=None)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def get_trace_context() -> dict[str, str]:
    ctx: dict[str, str] = {}
    tid = _trace_id.get()
    sid = _span_id.get()
    sess = _session_id.get()
    if tid:
        ctx["trace_id"] = tid
    if sid:
        ctx["span_id"] = sid
    if sess:
        ctx["session_id"] = sess
    from api.services.realtime_observability.correlation import get_call_id

    call_id = get_call_id()
    if call_id:
        ctx["call_id"] = call_id
    return ctx


@contextmanager
def trace_session(session_id: str, *, trace_id: str | None = None) -> Iterator[None]:
    """Bind trace + session context for the lifetime of a voice session."""
    token_trace = _trace_id.set(trace_id or new_trace_id())
    token_session = _session_id.set(session_id)
    token_span = _span_id.set(uuid.uuid4().hex[:16])
    try:
        yield
    finally:
        _trace_id.reset(token_trace)
        _session_id.reset(token_session)
        _span_id.reset(token_span)


@dataclass
class TraceSpan:
    """Lightweight span for stage timing (OpenTelemetry-compatible fields)."""

    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str | None = None
    start_mono: float = field(default_factory=time.monotonic)
    attributes: dict[str, Any] = field(default_factory=dict)
    _ended: bool = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def end(self) -> dict[str, Any]:
        if self._ended:
            return self.to_dict()
        self._ended = True
        duration_ms = (time.monotonic() - self.start_mono) * 1000.0
        self.attributes["duration_ms"] = round(duration_ms, 2)
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "attributes": self.attributes,
        }


class TracingHooks:
    """Callback registry for exporting spans to external systems (OTel, Langfuse, etc.)."""

    def __init__(self) -> None:
        self._exporters: list = []

    def register_exporter(self, fn) -> None:
        self._exporters.append(fn)

    def export_span(self, span: dict[str, Any]) -> None:
        for fn in self._exporters:
            try:
                fn(span)
            except Exception:
                pass

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[TraceSpan]:
        trace_id = _trace_id.get() or new_trace_id()
        parent = _span_id.get()
        attrs = dict(attributes)
        from api.services.realtime_observability.correlation import get_call_id

        call_id = get_call_id()
        if call_id and "call_id" not in attrs:
            attrs["call_id"] = call_id
        ts = TraceSpan(
            name=name,
            trace_id=trace_id,
            parent_span_id=parent,
            attributes=attrs,
        )
        token = _span_id.set(ts.span_id)
        try:
            yield ts
        finally:
            _span_id.reset(token)
            exported = ts.end()
            self.export_span(exported)


# Process-wide tracing hooks
TRACING = TracingHooks()
