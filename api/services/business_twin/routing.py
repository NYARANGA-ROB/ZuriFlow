"""Route customer questions to knowledge vs live tools. Minimum required data."""

from __future__ import annotations

from api.services.business_twin.types import DataPlane

_INVENTORY = ("stock", "in stock", "size ", "do you have", "available", "inventory")
_BOOKING = ("book", "appointment", "tomorrow", "available at", "slot", "reservation")
_ORDER = ("where is my order", "order status", "tracking", "delivery status", "shipment")
_PAYMENT = ("mpesa", "m-pesa", "payment", "paybill", "till", "did my payment")
_HOURS = ("close", "open", "hours", "what time")
_PRICE = ("how much", "price", "cost", "delivery fee", "charges")
_POLICY = ("refund", "policy", "return")
_SERVICES = ("what services", "what do you offer", "menu")


def route_query(query: str) -> dict[str, str]:
    q = (query or "").lower()
    if any(k in q for k in _PAYMENT) and any(
        k in q for k in ("did", "went through", "succeeded", "status", "confirm")
    ):
        return {"tool": "get_payment_status", "plane": DataPlane.LIVE.value}
    if any(k in q for k in _PAYMENT) and not any(k in q for k in ("did", "status")):
        return {"tool": "get_business_profile", "plane": DataPlane.KNOWLEDGE.value}
    if any(k in q for k in _INVENTORY):
        return {"tool": "check_inventory", "plane": DataPlane.LIVE.value}
    if any(k in q for k in _BOOKING):
        return {"tool": "check_appointment_availability", "plane": DataPlane.LIVE.value}
    if any(k in q for k in _ORDER):
        return {"tool": "get_order_status", "plane": DataPlane.LIVE.value}
    if any(k in q for k in _HOURS):
        return {"tool": "get_business_hours", "plane": DataPlane.KNOWLEDGE.value}
    if any(k in q for k in _PRICE):
        return {"tool": "get_price", "plane": DataPlane.KNOWLEDGE.value}
    if any(k in q for k in _POLICY):
        return {"tool": "get_business_policy", "plane": DataPlane.KNOWLEDGE.value}
    if any(k in q for k in _SERVICES):
        return {"tool": "get_service", "plane": DataPlane.KNOWLEDGE.value}
    return {"tool": "get_business_profile", "plane": DataPlane.KNOWLEDGE.value}


FALLBACK_MESSAGE = (
    "I don't have the latest information on that. Let me connect you with someone who can confirm."
)
