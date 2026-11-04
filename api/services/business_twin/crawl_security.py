"""SSRF-safe URL validation for website ingestion. Always blocks private IPs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from api.utils.url_security import _CGNAT_NETWORK, _is_blocked_saas_service_ip


class CrawlUrlError(ValueError):
    pass


PRIORITY_PATHS = (
    "/",
    "/about",
    "/services",
    "/products",
    "/pricing",
    "/contact",
    "/locations",
    "/faq",
    "/booking",
    "/delivery",
    "/policy",
    "/policies",
    "/menu",
)


def validate_crawl_url(url: str, *, resolve_dns: bool = True) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlUrlError("Website must be an http or https URL")
    host = parsed.hostname.lower()
    if host in {"localhost", "metadata.google.internal"}:
        raise CrawlUrlError("Website cannot target internal hosts")
    try:
        ipaddress.ip_address(host)
        resolve_dns = True
    except ValueError:
        pass
    if not resolve_dns:
        if host.endswith(".local") or host.endswith(".internal"):
            raise CrawlUrlError("Website cannot target internal hosts")
        return url
    try:
        ips = _resolve(host, parsed.port)
    except OSError as exc:
        raise CrawlUrlError("Could not resolve website hostname") from exc
    for ip in ips:
        if _is_blocked_saas_service_ip(ip) or ip in _CGNAT_NETWORK:
            raise CrawlUrlError("Website must resolve to a public address")
        if ip.version == 4 and ipaddress.ip_network("169.254.169.254/32").overlaps(
            ipaddress.ip_network(f"{ip}/32")
        ):
            raise CrawlUrlError("Website cannot target cloud metadata")
    return url


def _resolve(hostname: str, port: int | None) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass
    infos = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def is_priority_path(path: str) -> bool:
    lowered = (path or "/").lower().rstrip("/") or "/"
    return any(lowered == p or lowered.startswith(p + "/") for p in PRIORITY_PATHS)
