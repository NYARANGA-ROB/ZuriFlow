"""Kenya Data Protection Act / CAK-aligned consent checks."""

from __future__ import annotations

from datetime import UTC, datetime

from api.db import db_client
from api.services.omnichannel.types import Channel, ConsentDecision, MessagePurpose

_CHANNEL_OPT_OUT = {
    Channel.SMS: "sms_opt_out",
    Channel.WHATSAPP: "whatsapp_opt_out",
    Channel.VOICE: "voice_opt_out",
    Channel.WEB_CHAT: "webchat_opt_out",
}

LEGAL_NOTES = (
    "Kenya Data Protection Act, 2019 (ODPC): marketing needs a lawful basis "
    "and the right to object. CAK rules require a working opt-out for commercial SMS. "
    "Transactional notices (receipts, appointment reminders, missed-call follow-ups) "
    "use contract / legitimate interest unless the customer opted out of that channel."
)


class ConsentService:
    async def get_or_create(
        self,
        *,
        organization_id: int,
        customer_id: int,
        preferred_locale: str = "mixed",
    ):
        prefs = await db_client.get_preferences(
            organization_id=organization_id, customer_id=customer_id
        )
        if prefs:
            return prefs
        return await db_client.upsert_preferences(
            organization_id=organization_id,
            customer_id=customer_id,
            preferred_locale=preferred_locale,
            notes=LEGAL_NOTES,
            legal_basis="contract",
            transactional_consent=True,
            marketing_consent=False,
        )

    async def update(
        self,
        *,
        organization_id: int,
        customer_id: int,
        **fields,
    ):
        if fields.get("marketing_consent") is True and not fields.get("consent_recorded_at"):
            fields["consent_recorded_at"] = datetime.now(UTC)
            fields.setdefault("legal_basis", "consent")
        return await db_client.upsert_preferences(
            organization_id=organization_id,
            customer_id=customer_id,
            **fields,
        )

    async def decide(
        self,
        *,
        organization_id: int,
        customer_id: int | None,
        channel: Channel,
        purpose: MessagePurpose,
    ) -> ConsentDecision:
        if customer_id is None:
            if purpose == MessagePurpose.MARKETING:
                return ConsentDecision(
                    False,
                    "marketing_requires_identified_customer",
                    "none",
                    purpose.value,
                    channel.value,
                )
            return ConsentDecision(
                True,
                "transactional_anonymous_allowed",
                "legitimate_interest",
                purpose.value,
                channel.value,
            )

        prefs = await self.get_or_create(
            organization_id=organization_id, customer_id=customer_id
        )
        opt_out_field = _CHANNEL_OPT_OUT[channel]
        if getattr(prefs, opt_out_field, False):
            return ConsentDecision(
                False,
                f"{channel.value}_opted_out",
                prefs.legal_basis,
                purpose.value,
                channel.value,
            )
        if purpose == MessagePurpose.MARKETING:
            if not prefs.marketing_consent:
                return ConsentDecision(
                    False,
                    "marketing_consent_missing",
                    prefs.legal_basis,
                    purpose.value,
                    channel.value,
                )
            return ConsentDecision(
                True, "marketing_consent_granted", "consent", purpose.value, channel.value
            )
        if not prefs.transactional_consent:
            return ConsentDecision(
                False,
                "transactional_consent_revoked",
                prefs.legal_basis,
                purpose.value,
                channel.value,
            )
        return ConsentDecision(
            True,
            "transactional_allowed",
            prefs.legal_basis or "contract",
            purpose.value,
            channel.value,
        )


_consent: ConsentService | None = None


def get_consent_service() -> ConsentService:
    global _consent
    if _consent is None:
        _consent = ConsentService()
    return _consent
