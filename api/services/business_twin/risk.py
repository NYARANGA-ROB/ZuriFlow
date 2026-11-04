"""Risk classification for business data changes. LLMs never authorize critical."""

from __future__ import annotations

from api.services.business_twin.types import CRITICAL_FIELDS, HIGH_FIELDS, RiskLevel


def classify_risk(field_path: str, *, source: str = "") -> RiskLevel:
    path = (field_path or "").lower()
    src = (source or "").lower()
    if src == "ai_extraction" and any(k in path for k in CRITICAL_FIELDS):
        return RiskLevel.CRITICAL
    for key in CRITICAL_FIELDS:
        if key in path:
            return RiskLevel.CRITICAL
    for key in HIGH_FIELDS:
        if key in path:
            return RiskLevel.HIGH
    if "description" in path or "about" in path:
        return RiskLevel.MEDIUM
    if "faq" in path or "wording" in path:
        return RiskLevel.LOW
    return RiskLevel.MEDIUM


def requires_human_approval(
    risk: RiskLevel,
    *,
    confidence: float,
    medium_requires_approval: bool = False,
) -> bool:
    if risk == RiskLevel.CRITICAL:
        return True
    if risk == RiskLevel.HIGH:
        return True
    if risk == RiskLevel.MEDIUM:
        return medium_requires_approval or confidence < 0.85
    return confidence < 0.9


def auto_accept_allowed(risk: RiskLevel, *, confidence: float) -> bool:
    return risk == RiskLevel.LOW and confidence >= 0.9
