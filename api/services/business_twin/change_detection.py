"""Detect additions, deletions, and modifications between snapshots."""

from __future__ import annotations

from typing import Any

from api.services.business_twin.risk import classify_risk


def _flatten(prefix: str, value: Any, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            _flatten(path, nested, out)
        return
    if isinstance(value, list):
        out[prefix] = "|".join(str(item) for item in value)
        return
    out[prefix] = "" if value is None else str(value)


def flatten_record(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    _flatten("", data, out)
    return out


def detect_changes(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    source: str,
) -> list[dict[str, Any]]:
    old_map = flatten_record(previous or {})
    new_map = flatten_record(current)
    keys = set(old_map) | set(new_map)
    changes: list[dict[str, Any]] = []
    for key in sorted(keys):
        old_v = old_map.get(key)
        new_v = new_map.get(key)
        if old_v == new_v:
            continue
        if old_v is None:
            kind = "addition"
        elif new_v is None:
            kind = "deletion"
        else:
            kind = "modification"
        risk = classify_risk(key, source=source)
        changes.append(
            {
                "field_path": key,
                "old_value": old_v,
                "new_value": new_v,
                "kind": kind,
                "source": source,
                "risk_level": risk.value,
            }
        )
    return changes
