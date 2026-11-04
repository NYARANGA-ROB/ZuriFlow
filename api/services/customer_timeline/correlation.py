"""Customer correlation ID helpers for omnichannel events."""

from __future__ import annotations

from typing import Any

from api.utils.telephony_address import normalize_telephony_address


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    try:
        return normalize_telephony_address(str(phone)).canonical
    except Exception:
        digits = "".join(c for c in str(phone) if c.isdigit())
        return digits or None


def customer_correlation_id(phone_e164: str) -> str:
    phone = normalize_phone(phone_e164)
    if not phone:
        raise ValueError("phone_e164 required for customer correlation")
    return f"customer:{phone}"


def customer_uuid_correlation_id(customer_uuid: str) -> str:
    return f"customer_uuid:{customer_uuid}"


def customer_id_correlation_id(customer_id: int) -> str:
    return f"customer_id:{customer_id}"


async def resolve_phone_from_workflow_run(workflow_run_id: int) -> str | None:
    from api.db import db_client

    run = await db_client.get_workflow_run_by_id(workflow_run_id)
    if not run:
        return None
    ctx = run.initial_context or {}
    for key in ("caller_number", "called_number", "phone_number", "customer_phone"):
        phone = normalize_phone(ctx.get(key))
        if phone:
            return phone
    gathered = run.gathered_context or {}
    for key in ("caller_number", "phone_number", "customer_phone"):
        phone = normalize_phone(gathered.get(key))
        if phone:
            return phone
    return None


async def resolve_customer_context(
    organization_id: int,
    *,
    phone_e164: str | None = None,
    workflow_run_id: int | None = None,
    transaction_id: int | None = None,
    customer_id: int | None = None,
) -> dict[str, Any]:
    """Resolve phone, customer_id, and correlation_id for omnichannel events."""
    from api.db import db_client

    phone = normalize_phone(phone_e164)
    resolved_customer_id = customer_id

    if not phone and workflow_run_id:
        phone = await resolve_phone_from_workflow_run(workflow_run_id)

    if not phone and transaction_id:
        txn = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if txn:
            phone = normalize_phone(txn.phone_e164)

    if resolved_customer_id is None and phone:
        customer = await db_client.get_customer_by_phone(
            organization_id=organization_id,
            phone_e164=phone,
        )
        if customer:
            resolved_customer_id = customer.id

    correlation_id = customer_correlation_id(phone) if phone else None
    return {
        "phone_e164": phone,
        "customer_id": resolved_customer_id,
        "correlation_id": correlation_id,
    }
