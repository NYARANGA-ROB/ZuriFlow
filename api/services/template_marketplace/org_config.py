"""Org configuration normalization for template overrides."""

from __future__ import annotations

from typing import Any


def normalize_org_config(value: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize flat legacy wizard config into nested templates shape."""
    if not value:
        return {"templates": {}}
    if "templates" in value:
        return value
    templates: dict[str, Any] = {}
    for key, cfg in value.items():
        if isinstance(cfg, dict) and key not in ("templates",):
            templates[key] = cfg
    return {"templates": templates}
