"""Data quality scores per category — never a single unexplained number."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.services.business_twin.freshness import freshness_score


def _pct(parts: list[float]) -> int:
    if not parts:
        return 0
    return int(round(sum(parts) / len(parts) * 100))


def score_profile(profile: dict[str, Any]) -> dict[str, Any]:
    fields = ["legal_name", "industry", "hours", "languages", "payment"]
    present = [1.0 if profile.get(f) else 0.0 for f in fields]
    score, status = freshness_score(
        last_verified_at=_parse(profile.get("last_verified_at")),
    )
    return {
        "completeness": _pct(present),
        "freshness": int(score * 100),
        "status": status,
        "score": _pct([sum(present) / len(present), score]),
    }


def score_collection(rows: list, *, verified_attr: str = "status") -> dict[str, Any]:
    if not rows:
        return {"completeness": 0, "freshness": 0, "score": 0, "count": 0}
    verified = 0
    fresh: list[float] = []
    for row in rows:
        status = getattr(row, verified_attr, None) or (row.get(verified_attr) if isinstance(row, dict) else None)
        if status == "verified":
            verified += 1
        last = getattr(row, "last_verified_at", None)
        s, _ = freshness_score(last_verified_at=last)
        fresh.append(s)
    completeness = verified / len(rows)
    freshness = sum(fresh) / len(fresh)
    return {
        "completeness": int(completeness * 100),
        "freshness": int(freshness * 100),
        "score": _pct([completeness, freshness]),
        "count": len(rows),
    }


def overall(categories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scores = [float(v.get("score") or 0) / 100 for v in categories.values()]
    return {"overall": _pct(scores), "categories": categories}


def _parse(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
