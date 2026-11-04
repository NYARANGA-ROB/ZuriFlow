"""Configurable source authority. AI extraction never outranks live systems."""

from __future__ import annotations

from api.services.business_twin.types import DEFAULT_AUTHORITY, SourceType


def rank_sources(data_type: str, ranked: list[str] | None = None) -> list[str]:
    order = list(ranked) if ranked else list(DEFAULT_AUTHORITY.get(data_type, DEFAULT_AUTHORITY["default"]))
    ai = SourceType.AI_EXTRACTION.value
    if ai in order:
        order = [s for s in order if s != ai] + [ai]
    return order


def preferred_source(
    data_type: str,
    candidates: dict[str, str],
    ranked: list[str] | None = None,
) -> tuple[str | None, str | None]:
    """Return (source, value) for the highest-ranked candidate."""
    order = rank_sources(data_type, ranked)
    for source in order:
        if source in candidates:
            return source, candidates[source]
    if candidates:
        item = next(iter(candidates.items()))
        return item[0], item[1]
    return None, None
