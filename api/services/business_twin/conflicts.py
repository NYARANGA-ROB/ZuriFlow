"""Conflict records when two sources disagree and none is auto-selected."""

from __future__ import annotations

from typing import Any


def detect_conflict(
    field_path: str,
    values_by_source: dict[str, str],
) -> dict[str, Any] | None:
    unique = {v for v in values_by_source.values() if v is not None and str(v).strip()}
    if len(unique) <= 1 or len(values_by_source) < 2:
        return None
    items = list(values_by_source.items())
    return {
        "field_path": field_path,
        "source_a": items[0][0],
        "value_a": items[0][1],
        "source_b": items[1][0],
        "value_b": items[1][1],
        "resolution_status": "open",
    }


def resolve_with_authority(
    field_path: str,
    values_by_source: dict[str, str],
    *,
    data_type: str,
    ranked: list[str] | None = None,
) -> dict[str, Any] | None:
    """Keep the conflict visible but select the authoritative value."""
    from api.services.business_twin.authority import preferred_source

    conflict = detect_conflict(field_path, values_by_source)
    if conflict is None:
        return None
    winner, value = preferred_source(data_type, values_by_source, ranked)
    conflict["authoritative_source"] = winner
    conflict["authoritative_value"] = value
    conflict["alert"] = True
    return conflict
