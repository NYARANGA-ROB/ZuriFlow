"""Resolve and merge customer identities across channels."""

from __future__ import annotations

from uuid import uuid4

from api.db import db_client
from api.services.customer_timeline.correlation import normalize_phone
from api.services.omnichannel.types import IdentityKind, IdentityMatch


def _norm_email(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower() or None


class CustomerIdentityService:
    """Link phone, email, WhatsApp, CRM, and customer IDs to one record."""

    async def resolve(
        self,
        *,
        organization_id: int,
        phone: str | None = None,
        email: str | None = None,
        whatsapp_id: str | None = None,
        crm_id: str | None = None,
        customer_id: int | None = None,
        full_name: str | None = None,
        preferred_locale: str = "mixed",
    ) -> IdentityMatch:
        candidates: dict[int, str] = {}
        claims: list[tuple[IdentityKind, str]] = []

        phone_e164 = normalize_phone(phone) if phone else None
        email_n = _norm_email(email)
        wa = (whatsapp_id or phone_e164 or "").strip() or None
        crm = (crm_id or "").strip() or None

        if customer_id:
            existing = await db_client.get_customer(customer_id, organization_id=organization_id)
            if existing:
                candidates[existing.id] = "customer"
                claims.append((IdentityKind.CUSTOMER, str(existing.id)))

        lookups = [
            (IdentityKind.PHONE, phone_e164),
            (IdentityKind.EMAIL, email_n),
            (IdentityKind.WHATSAPP, wa),
            (IdentityKind.CRM, crm),
        ]
        for kind, value in lookups:
            if not value:
                continue
            claims.append((kind, value))
            ident = await db_client.get_identity(
                organization_id=organization_id, kind=kind.value, value=value
            )
            if ident:
                candidates[ident.customer_id] = kind.value

        if phone_e164 and not any(k == "phone" for k in candidates.values()):
            by_phone = await db_client.get_customer_by_phone(
                organization_id=organization_id, phone_e164=phone_e164
            )
            if by_phone:
                candidates[by_phone.id] = "phone"

        created = False
        merged_from: list[int] = []
        if not candidates:
            customer = await db_client.create_customer(
                organization_id=organization_id,
                phone_e164=phone_e164 or f"unknown-{uuid4().hex[:12]}",
                full_name=full_name or "Kenyan customer",
                email=email_n,
                preferred_locale=preferred_locale,
                external_crm_id=crm,
            )
            canonical_id = customer.id
            created = True
        else:
            canonical_id = min(candidates)
            extras = [cid for cid in candidates if cid != canonical_id]
            for extra in extras:
                await db_client.reassign_identities(
                    organization_id=organization_id,
                    from_customer_id=extra,
                    to_customer_id=canonical_id,
                )
                await db_client.update_customer(
                    extra,
                    organization_id=organization_id,
                    is_active=False,
                    metadata={"merged_into": canonical_id},
                )
                merged_from.append(extra)

        identity_rows: list[dict[str, str]] = []
        if phone_e164:
            await db_client.upsert_identity(
                organization_id=organization_id,
                customer_id=canonical_id,
                kind=IdentityKind.PHONE.value,
                value=phone_e164,
                is_primary=True,
            )
        if email_n:
            await db_client.upsert_identity(
                organization_id=organization_id,
                customer_id=canonical_id,
                kind=IdentityKind.EMAIL.value,
                value=email_n,
            )
        if wa:
            await db_client.upsert_identity(
                organization_id=organization_id,
                customer_id=canonical_id,
                kind=IdentityKind.WHATSAPP.value,
                value=wa,
            )
        if crm:
            await db_client.upsert_identity(
                organization_id=organization_id,
                customer_id=canonical_id,
                kind=IdentityKind.CRM.value,
                value=crm,
            )
        await db_client.upsert_identity(
            organization_id=organization_id,
            customer_id=canonical_id,
            kind=IdentityKind.CUSTOMER.value,
            value=str(canonical_id),
            is_primary=True,
        )

        stored = await db_client.list_identities_for_customer(
            organization_id=organization_id, customer_id=canonical_id
        )
        identity_rows = [{"kind": i.kind, "value": i.value} for i in stored]
        return IdentityMatch(
            customer_id=canonical_id,
            created=created,
            merged_from=merged_from,
            identities=identity_rows,
        )


_identity: CustomerIdentityService | None = None


def get_customer_identity_service() -> CustomerIdentityService:
    global _identity
    if _identity is None:
        _identity = CustomerIdentityService()
    return _identity
