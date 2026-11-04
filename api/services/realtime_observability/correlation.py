"""Call-wide correlation IDs for Browser → API → Pipecat → STT/LLM/TTS → tools → DB → workers."""

from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

_call_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("call_id", default=None)
_org_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("call_org_id", default=None)
_run_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("call_run_id", default=None)


def new_call_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class CallCorrelation:
    call_id: str
    session_id: str
    organization_id: int = 0
    workflow_run_id: int = 0
    trace_id: str = ""

    def as_log_extra(self) -> dict[str, str | int]:
        return {
            "call_id": self.call_id,
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id or self.call_id,
        }

    def as_headers(self) -> dict[str, str]:
        return {
            "X-Call-Id": self.call_id,
            "X-Trace-Id": self.trace_id or self.call_id,
            "X-Session-Id": self.session_id,
        }


def install_call_correlation(corr: CallCorrelation) -> None:
    """Bind correlation for the remainder of the current asyncio task."""
    _call_id.set(corr.call_id)
    _org_id.set(corr.organization_id or None)
    _run_id.set(corr.workflow_run_id or None)


def get_call_id() -> str | None:
    return _call_id.get()


def get_call_organization_id() -> int | None:
    return _org_id.get()


@contextmanager
def bind_call_correlation(corr: CallCorrelation) -> Iterator[CallCorrelation]:
    t_call = _call_id.set(corr.call_id)
    t_org = _org_id.set(corr.organization_id or None)
    t_run = _run_id.set(corr.workflow_run_id or None)
    try:
        yield corr
    finally:
        _call_id.reset(t_call)
        _org_id.reset(t_org)
        _run_id.reset(t_run)


def correlation_from_session(
    *,
    session_id: str,
    organization_id: int = 0,
    workflow_run_id: int = 0,
    call_id: str | None = None,
    trace_id: str | None = None,
) -> CallCorrelation:
    cid = call_id or new_call_id()
    return CallCorrelation(
        call_id=cid,
        session_id=session_id,
        organization_id=organization_id,
        workflow_run_id=workflow_run_id,
        trace_id=trace_id or cid,
    )
