from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def fire_and_forget(coro: Awaitable[Any], *, name: str = "bg-task") -> None:
    """Schedule non-critical async work without blocking the voice hot path."""

    async def _wrapper() -> None:
        try:
            await coro
        except Exception:
            pass

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_wrapper(), name=name)
    except RuntimeError:
        try:
            coro.close()  # type: ignore[attr-defined]
        except Exception:
            pass


async def gather_with_concurrency(
    items: list[T],
    worker: Callable[[T], Awaitable[Any]],
    *,
    limit: int = 10,
) -> list[Any]:
    """Run async workers with a concurrency cap (cost + reliability control)."""
    sem = asyncio.Semaphore(limit)
    results: list[Any] = []

    async def _run(item: T) -> Any:
        async with sem:
            return await worker(item)

    results = await asyncio.gather(*[_run(i) for i in items], return_exceptions=True)
    return results
