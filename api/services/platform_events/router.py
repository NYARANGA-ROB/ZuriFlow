"""Async event router with handler registry and retries."""

from __future__ import annotations

from collections import defaultdict
from typing import Awaitable, Callable

from loguru import logger

from api.constants import (
    PLATFORM_EVENTS_MAX_HANDLER_RETRIES,
    PLATFORM_EVENTS_RETRY_BASE_DELAY_S,
)
from api.services.platform_events.dlq import get_platform_event_dlq
from api.services.platform_events.observability import get_platform_event_observability
from api.services.platform_events.schema import PlatformEvent, PlatformEventType

EventHandler = Callable[[PlatformEvent], Awaitable[None]]


class PlatformEventRouter:
    """Route typed events to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[PlatformEventType, list[tuple[str, EventHandler]]] = (
            defaultdict(list)
        )

    def register(
        self,
        event_type: PlatformEventType,
        handler: EventHandler,
        *,
        name: str | None = None,
    ) -> None:
        handler_name = name or getattr(handler, "__name__", "anonymous")
        self._handlers[event_type].append((handler_name, handler))

    def registered_types(self) -> list[str]:
        return sorted(t.value for t in self._handlers.keys())

    async def dispatch(
        self,
        event: PlatformEvent,
        *,
        handler_name: str | None = None,
        attempt: int = 1,
    ) -> dict[str, int]:
        handlers = self._handlers.get(event.event_type, [])
        if handler_name:
            handlers = [(n, h) for n, h in handlers if n == handler_name]

        if not handlers:
            logger.debug(
                "no handlers for platform event type={} event_id={}",
                event.event_type.value,
                event.event_id,
            )
            return {"handled": 0, "failed": 0, "skipped": 1}

        handled = 0
        failed = 0
        obs = get_platform_event_observability()
        dlq = get_platform_event_dlq()

        for name, handler in handlers:
            try:
                await handler(event)
                handled += 1
                await obs.record_handled(event, handler_name=name)
            except Exception as exc:
                failed += 1
                await obs.record_failed(event, handler_name=name, error=str(exc))
                logger.warning(
                    "platform event handler failed type={} handler={} attempt={}: {}",
                    event.event_type.value,
                    name,
                    attempt,
                    exc,
                )
                if attempt < PLATFORM_EVENTS_MAX_HANDLER_RETRIES:
                    delay = PLATFORM_EVENTS_RETRY_BASE_DELAY_S * (
                        2 ** max(0, attempt - 1)
                    )
                    await dlq.schedule_retry(
                        event,
                        handler_name=name,
                        attempt=attempt + 1,
                        delay_s=delay,
                    )
                else:
                    await dlq.enqueue(
                        event,
                        handler_name=name,
                        error=str(exc),
                        attempts=attempt,
                    )
        return {"handled": handled, "failed": failed, "skipped": 0}


_router: PlatformEventRouter | None = None


def get_platform_event_router() -> PlatformEventRouter:
    global _router
    if _router is None:
        _router = PlatformEventRouter()
        from api.services.platform_events.handlers import register_builtin_handlers

        register_builtin_handlers(_router)
    return _router
