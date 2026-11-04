from __future__ import annotations

import asyncio
import functools
from typing import Any, Awaitable, Callable, TypeVar

from loguru import logger

from api.constants import MPESA_RETRY_BASE_DELAY_S, MPESA_RETRY_MAX_ATTEMPTS

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_ERROR_FRAGMENTS = (
    "timeout",
    "temporarily",
    "rate limit",
    "connection",
    "unavailable",
)


def _is_retryable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(fragment in message for fragment in RETRYABLE_ERROR_FRAGMENTS)


def with_daraja_retry(
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Retry middleware for transient Daraja API failures."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        last_error: Exception | None = None
        for attempt in range(1, MPESA_RETRY_MAX_ATTEMPTS + 1):
            try:
                return await func(*args, **kwargs)
            except (aiohttp_client_error(), asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt >= MPESA_RETRY_MAX_ATTEMPTS or not _is_retryable(exc):
                    raise
                delay = MPESA_RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.warning(
                    "Daraja call {} failed attempt {}/{}: {} — retrying in {}s",
                    func.__name__,
                    attempt,
                    MPESA_RETRY_MAX_ATTEMPTS,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        if last_error:
            raise last_error
        raise RuntimeError("Daraja retry exhausted")

    return wrapper


def aiohttp_client_error():
    try:
        import aiohttp

        return aiohttp.ClientError
    except ImportError:
        return Exception
