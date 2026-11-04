"""Generic REST connector: only pre-approved endpoints on allowlisted HTTPS hosts."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from api.services.business_twin.connector_types import DATA_UNAVAILABLE, validate_response
from api.services.business_twin.crawl_security import CrawlUrlError, validate_crawl_url

ALLOWED_METHODS = frozenset({"GET", "POST", "PATCH"})
MAX_RESPONSE_BYTES = 64_000
TIMEOUT_S = 5.0


class RestConnectorError(ValueError):
    pass


def build_url(host: str, path: str, *, https_only: bool = True) -> str:
    path = path if path.startswith("/") else f"/{path}"
    scheme = "https" if https_only else "https"
    return f"{scheme}://{host}{path}"


def assert_allowlisted(url: str, hosts: list[str]) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = {h.lower() for h in hosts}
    if host not in allowed:
        raise RestConnectorError("Host is not on the approved list")
    if parsed.scheme != "https":
        raise RestConnectorError("HTTPS is required")
    validate_crawl_url(url)


def substitute_path(path: str, arguments: dict[str, Any]) -> str:
    out = path
    for key, value in arguments.items():
        if not isinstance(value, (str, int, float)):
            continue
        token = "{" + key + "}"
        if token in out:
            out = out.replace(token, str(value))
    if "{" in out and "}" in out:
        raise RestConnectorError("Missing required path parameter")
    return out


async def invoke_rest_endpoint(
    *,
    host: str,
    hosts: list[str],
    endpoint: dict[str, Any],
    arguments: dict[str, Any],
    headers: dict[str, str] | None = None,
    http_client=None,
) -> dict[str, Any]:
    method = str(endpoint.get("method") or "GET").upper()
    if method not in ALLOWED_METHODS:
        raise RestConnectorError("Method is not allowed")
    path = substitute_path(str(endpoint.get("path") or "/"), arguments)
    url = build_url(host, path)
    assert_allowlisted(url, hosts)
    required = list(endpoint.get("required_fields") or [])
    started = time.perf_counter()
    client = http_client
    owns = False
    if client is None:
        client = httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False)
        owns = True
    try:
        if method == "GET":
            response = await client.get(url, headers=headers or {})
        elif method == "POST":
            response = await client.post(url, json=arguments, headers=headers or {})
        else:
            response = await client.patch(url, json=arguments, headers=headers or {})
    except CrawlUrlError as exc:
        raise RestConnectorError(str(exc)) from exc
    finally:
        if owns:
            await client.aclose()
    latency_ms = int((time.perf_counter() - started) * 1000)
    content = response.content or b""
    if len(content) > MAX_RESPONSE_BYTES:
        return {**DATA_UNAVAILABLE, "latency_ms": latency_ms, "reason": "oversized"}
    if response.status_code >= 400:
        return {**DATA_UNAVAILABLE, "latency_ms": latency_ms, "reason": "http_error"}
    try:
        payload = response.json()
    except Exception:
        return {**DATA_UNAVAILABLE, "latency_ms": latency_ms, "reason": "invalid_json"}
    if not isinstance(payload, dict):
        payload = {"data": payload}
    checked = validate_response(payload, required)
    if checked is None:
        return {**DATA_UNAVAILABLE, "latency_ms": latency_ms, "reason": "schema"}
    checked["verified"] = True
    checked["plane"] = "live"
    checked["latency_ms"] = latency_ms
    return checked
