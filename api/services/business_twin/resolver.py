"""Central live-vs-knowledge decision. Extends v1 route_query; does not replace tools."""

from __future__ import annotations

from dataclasses import dataclass

from api.services.business_twin.routing import route_query
from api.services.business_twin.types import DataPlane


@dataclass
class Resolution:
    intent: str
    plane: str
    tool: str
    source: str
    authority: str
    reason: str
    confidence: float


_INTENT = {
    "get_business_hours": "BUSINESS_HOURS",
    "check_inventory": "PRODUCT_AVAILABILITY",
    "check_appointment_availability": "BOOKING",
    "get_payment_status": "PAYMENT_STATUS",
    "get_price": "PRICE",
    "get_business_policy": "POLICY",
    "get_service": "SERVICES",
    "get_order_status": "ORDER_STATUS",
    "get_delivery_status": "DELIVERY",
    "get_current_promotions": "PROMOTIONS",
    "get_branch_information": "BRANCH",
    "get_business_profile": "PROFILE",
}


def resolve_information(query: str, *, live_price: bool = False) -> Resolution:
    routed = route_query(query)
    tool = routed["tool"]
    plane = routed["plane"]
    q = (query or "").lower()
    if "open tomorrow" in q or "are you open" in q:
        tool, plane = "get_business_hours", DataPlane.KNOWLEDGE.value
    if live_price and tool == "get_price":
        plane = DataPlane.LIVE.value
        source = "inventory_api"
        authority = "HIGH"
        reason = "Configured live price source outranks documents"
    elif plane == DataPlane.LIVE.value:
        source = {
            "check_inventory": "inventory_api",
            "check_appointment_availability": "booking_api",
            "get_payment_status": "payment_provider",
            "get_order_status": "order_api",
            "get_delivery_status": "order_api",
        }.get(tool, "live")
        authority = "HIGH"
        reason = "Operational question requires an authoritative live system"
    else:
        source = "approved_knowledge"
        authority = "MEDIUM"
        reason = "Stable business fact from approved knowledge"
        if tool == "get_business_policy":
            authority = "HIGH"
            reason = "Approved policy knowledge"
    return Resolution(
        intent=_INTENT.get(tool, "GENERAL"),
        plane=plane,
        tool=tool,
        source=source,
        authority=authority,
        reason=reason,
        confidence=0.9 if plane == DataPlane.LIVE.value else 0.82,
    )
