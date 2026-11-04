"""Website ingestion: validate, prioritize pages, extract, never follow private redirects."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from loguru import logger

from api.constants import BUSINESS_TWIN_CRAWL_MAX_PAGES, BUSINESS_TWIN_CRAWL_TIMEOUT_S
from api.services.business_twin.crawl_security import (
    PRIORITY_PATHS,
    CrawlUrlError,
    is_priority_path,
    validate_crawl_url,
)
from api.services.business_twin.extractors import extract_from_html

USER_AGENT = "ZuriFlowBusinessBot/1.0 (+https://zuriflow.example/bot)"


async def ingest_website(url: str, *, fetch=None) -> dict[str, Any]:
    resolve_dns = fetch is None
    validate_crawl_url(url, resolve_dns=resolve_dns)
    fetch = fetch or _http_get
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    robots_ok = await _robots_allows(origin, fetch)
    pages: list[dict[str, Any]] = []
    candidates = [url]
    for path in PRIORITY_PATHS:
        candidates.append(urljoin(origin, path))
    seen: set[str] = set()
    for candidate in candidates:
        if len(pages) >= BUSINESS_TWIN_CRAWL_MAX_PAGES:
            break
        try:
            validate_crawl_url(candidate, resolve_dns=resolve_dns)
        except CrawlUrlError:
            continue
        path = urlparse(candidate).path or "/"
        if candidate in seen or not is_priority_path(path):
            continue
        if robots_ok is False:
            break
        seen.add(candidate)
        try:
            html = await fetch(candidate)
        except Exception as exc:
            logger.info("Website fetch skipped for {}: {}", candidate, exc)
            continue
        if not html:
            continue
        extracted = extract_from_html(html, source_url=candidate)
        pages.append({"url": candidate, "extraction": extracted})
        for href in _links(html, origin)[:8]:
            if href not in seen:
                candidates.append(href)
    merged = _merge_pages(pages)
    return {
        "origin": origin,
        "pages": pages,
        "merged": merged,
        "status": "pending_review",
        "source_type": "website",
    }


async def _robots_allows(origin: str, fetch) -> bool | None:
    try:
        body = await fetch(urljoin(origin, "/robots.txt"))
    except Exception:
        return None
    if not body:
        return None
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    return parser.can_fetch(USER_AGENT, origin + "/")


def _links(html: str, origin: str) -> list[str]:
    found = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    out: list[str] = []
    for href in found:
        abs_url = urljoin(origin, href)
        if abs_url.startswith(origin):
            out.append(abs_url.split("#")[0])
    return out


def _merge_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    phones: list[str] = []
    services: list[str] = []
    faqs: list[dict] = []
    hours: list[str] = []
    for page in pages:
        ext = page.get("extraction") or {}
        phones.extend(ext.get("phones") or [])
        services.extend(ext.get("services") or [])
        faqs.extend(ext.get("faqs") or [])
        hours.extend(ext.get("hours_mentions") or [])
    return {
        "phones": list(dict.fromkeys(phones)),
        "services": list(dict.fromkeys(services)),
        "faqs": faqs[:12],
        "hours_mentions": hours[:8],
        "confidence": 0.74 if pages else 0.0,
    }


async def _http_get(url: str) -> str:
    import httpx

    validate_crawl_url(url)
    async with httpx.AsyncClient(
        timeout=BUSINESS_TWIN_CRAWL_TIMEOUT_S,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(url)
        if response.is_redirect:
            location = response.headers.get("location", "")
            if location:
                validate_crawl_url(str(response.url.join(location)))
            raise CrawlUrlError("Redirects are not followed automatically")
        response.raise_for_status()
        return response.text[:400_000]
