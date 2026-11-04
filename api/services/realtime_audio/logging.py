"""Structured logging helpers for realtime audio sessions."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from loguru import logger


@contextmanager
def session_log_context(
    session_id: str,
    *,
    client_id: str | None = None,
    resumed: bool = False,
) -> Iterator[None]:
    """Bind session fields to loguru context for the duration of a block."""
    extra = {"session_id": session_id, "resumed": resumed}
    if client_id:
        extra["client_id"] = client_id
    with logger.contextualize(**extra):
        yield


def log_connect(session_id: str, *, client_id: str | None, resumed: bool) -> None:
    logger.info(
        "realtime_audio connect session_id={} client_id={} resumed={}",
        session_id,
        client_id or "-",
        resumed,
    )


def log_disconnect(
    session_id: str,
    *,
    reason: str,
    code: int | None = None,
    graceful: bool = True,
) -> None:
    logger.info(
        "realtime_audio disconnect session_id={} reason={} code={} graceful={}",
        session_id,
        reason,
        code,
        graceful,
    )


def log_chunk(
    session_id: str,
    *,
    direction: str,
    seq: int,
    nbytes: int,
    dropped: bool = False,
) -> None:
    logger.debug(
        "realtime_audio chunk session_id={} dir={} seq={} bytes={} dropped={}",
        session_id,
        direction,
        seq,
        nbytes,
        dropped,
    )


def log_heartbeat(session_id: str, *, event: str, latency_ms: float | None = None) -> None:
    logger.debug(
        "realtime_audio heartbeat session_id={} event={} latency_ms={}",
        session_id,
        event,
        latency_ms,
    )


def log_error(session_id: str, message: str, *, exc: Exception | None = None) -> None:
    if exc:
        logger.opt(exception=exc).error(
            "realtime_audio error session_id={} msg={}", session_id, message
        )
    else:
        logger.error("realtime_audio error session_id={} msg={}", session_id, message)
