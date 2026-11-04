from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from api.constants import ORG_CONFIG_CACHE_TTL_S

T = TypeVar("T")


@dataclass
class OrgConfigCache(Generic[T]):
    """Short-TTL in-process cache to cut repeated DB reads during calls."""

    ttl_s: float = ORG_CONFIG_CACHE_TTL_S
    max_entries: int = 256
    _data: dict[tuple[int, str], tuple[float, T]] = field(default_factory=dict)

    def get(self, organization_id: int, key: str) -> T | None:
        entry = self._data.get((organization_id, key))
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            self._data.pop((organization_id, key), None)
            return None
        return value

    def set(self, organization_id: int, key: str, value: T) -> None:
        if len(self._data) >= self.max_entries:
            oldest = min(self._data.items(), key=lambda kv: kv[1][0])
            self._data.pop(oldest[0], None)
        self._data[(organization_id, key)] = (time.monotonic() + self.ttl_s, value)

    def invalidate(self, organization_id: int, key: str | None = None) -> None:
        if key is None:
            to_drop = [k for k in self._data if k[0] == organization_id]
            for k in to_drop:
                self._data.pop(k, None)
            return
        self._data.pop((organization_id, key), None)


_mpesa_cache: OrgConfigCache[Any] = OrgConfigCache()
_whatsapp_cache: OrgConfigCache[Any] = OrgConfigCache()
_routing_cache: OrgConfigCache[Any] = OrgConfigCache()


def mpesa_config_cache() -> OrgConfigCache[Any]:
    return _mpesa_cache


def whatsapp_config_cache() -> OrgConfigCache[Any]:
    return _whatsapp_cache


def routing_config_cache() -> OrgConfigCache[Any]:
    return _routing_cache
