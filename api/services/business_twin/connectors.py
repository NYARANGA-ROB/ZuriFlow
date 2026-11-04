"""Provider-independent live data connectors. Workflows call check_inventory, not vendor APIs."""

from __future__ import annotations

from typing import Any, Protocol

from api.db import db_client


class InventoryProvider(Protocol):
    async def check_inventory(self, sku: str, *, organization_id: int) -> dict[str, Any]: ...


class BookingProvider(Protocol):
    async def check_availability(
        self, when_iso: str, *, organization_id: int, branch: str | None = None
    ) -> dict[str, Any]: ...


class CrmProvider(Protocol):
    async def get_customer(self, phone: str, *, organization_id: int) -> dict[str, Any]: ...


class OrderProvider(Protocol):
    async def get_order(self, order_id: str, *, organization_id: int) -> dict[str, Any]: ...


class PaymentProvider(Protocol):
    async def get_payment_status(
        self, reference: str, *, organization_id: int
    ) -> dict[str, Any]: ...


class AccountingProvider(Protocol):
    async def get_invoice(self, invoice_id: str, *, organization_id: int) -> dict[str, Any]: ...


class SnapshotInventory:
    def __init__(self, items: dict[str, dict[str, Any]] | None = None) -> None:
        self.items = items or {}

    async def check_inventory(self, sku: str, *, organization_id: int) -> dict[str, Any]:
        item = self.items.get(sku.lower()) or self.items.get(sku)
        if not item:
            return {
                "sku": sku,
                "in_stock": None,
                "plane": "live",
                "verified": False,
                "message": "I don't have the latest stock information. Let me connect you with someone who can confirm.",
            }
        return {"sku": sku, "in_stock": bool(item.get("qty", 0) > 0), "qty": item.get("qty"), "plane": "live", "verified": True}


class SnapshotBooking:
    def __init__(self, slots: dict[str, bool] | None = None) -> None:
        self.slots = slots or {}

    async def check_availability(
        self, when_iso: str, *, organization_id: int, branch: str | None = None
    ) -> dict[str, Any]:
        key = f"{branch or 'default'}|{when_iso}"
        if key not in self.slots and when_iso not in self.slots:
            return {
                "when": when_iso,
                "available": None,
                "plane": "live",
                "verified": False,
                "message": "I don't have the latest booking calendar. Let me connect you with someone who can confirm.",
            }
        available = self.slots.get(key, self.slots.get(when_iso, False))
        return {"when": when_iso, "available": available, "plane": "live", "verified": True}


class InternalCrmAdapter:
    async def get_customer(self, phone: str, *, organization_id: int) -> dict[str, Any]:
        from api.services.kenya.phone import normalize_kenyan_phone

        parsed = normalize_kenyan_phone(phone)
        e164 = parsed.e164 if parsed.valid else phone
        customer = await db_client.get_customer_by_phone(
            organization_id=organization_id, phone_e164=e164
        )
        if customer is None:
            return {"found": False, "plane": "live", "verified": True}
        return {
            "found": True,
            "customer_id": customer.id,
            "full_name": customer.full_name,
            "plane": "live",
            "verified": True,
        }


class InternalPaymentAdapter:
    async def get_payment_status(self, reference: str, *, organization_id: int) -> dict[str, Any]:
        tx = None
        if reference.isdigit():
            tx = await db_client.get_transaction(int(reference), organization_id=organization_id)
        if tx is None:
            tx = await db_client.get_transaction_by_checkout_request_id(
                reference, organization_id=organization_id
            )
        if tx is None:
            return {
                "found": False,
                "plane": "live",
                "verified": True,
                "message": "I could not find that payment. Let me connect you with someone who can confirm.",
            }
        return {
            "found": True,
            "status": tx.status,
            "amount": tx.amount,
            "currency": tx.currency,
            "plane": "live",
            "verified": True,
        }


class HttpOrderAdapter:
    """Generic HTTP adapter — URL comes from the connected system, not the workflow."""

    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records = records or {}

    async def get_order(self, order_id: str, *, organization_id: int) -> dict[str, Any]:
        rec = self.records.get(order_id)
        if not rec:
            return {
                "found": False,
                "plane": "live",
                "verified": False,
                "message": "I don't have the latest order status. Let me connect you with someone who can confirm.",
            }
        return {"found": True, **rec, "plane": "live", "verified": True}


def providers_from_snapshots(inventory: dict | None, bookings: dict | None, orders: dict | None) -> dict[str, Any]:
    return {
        "inventory": SnapshotInventory(inventory),
        "booking": SnapshotBooking(bookings),
        "crm": InternalCrmAdapter(),
        "order": HttpOrderAdapter(orders),
        "payment": InternalPaymentAdapter(),
    }
