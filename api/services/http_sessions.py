"""Shared aiohttp sessions for external APIs (connection reuse, lower latency)."""

from __future__ import annotations

import asyncio

import aiohttp

_session: aiohttp.ClientSession | None = None
_lock = asyncio.Lock()


async def get_shared_http_session() -> aiohttp.ClientSession:
    global _session
    if _session is not None and not _session.closed:
        return _session
    async with _lock:
        if _session is None or _session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=8, sock_read=25)
            connector = aiohttp.TCPConnector(limit=80, ttl_dns_cache=300)
            _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_shared_http_session() -> None:
    global _session
    async with _lock:
        if _session is not None and not _session.closed:
            await _session.close()
        _session = None
