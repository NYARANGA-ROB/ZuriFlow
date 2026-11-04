"""Customer omnichannel timeline service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.constants import CUSTOMER_TIMELINE_ENABLED
from api.db import db_client
from api.services.customer_timeline.correlation import (
    normalize_phone,
    resolve_customer_context,
)
from api.services.customer_timeline.state_machine import active_channels, derive_journey_state
from api.services.customer_timeline.types import (
    CustomerJourneyState,
    CustomerTimeline,
    TimelineChannel,
    TimelineEntry,
)


class CustomerTimelineService:
    @property
    def enabled(self) -> bool:
        return CUSTOMER_TIMELINE_ENABLED

    async def get_by_customer_id(
        self,
        customer_id: int,
        *,
        organization_id: int,
        days: int = 30,
        limit: int = 100,
    ) -> CustomerTimeline | None:
        customer = await db_client.get_customer(customer_id, organization_id=organization_id)
        if customer is None:
            return None
        return await self._build_timeline(
            organization_id=organization_id,
            phone_e164=customer.phone_e164,
            customer_id=customer.id,
            customer_uuid=customer.customer_uuid,
            full_name=customer.full_name,
            days=days,
            limit=limit,
        )

    async def get_by_phone(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        days: int = 30,
        limit: int = 100,
    ) -> CustomerTimeline:
        phone = normalize_phone(phone_e164) or phone_e164
        customer = await db_client.get_customer_by_phone(
            organization_id=organization_id,
            phone_e164=phone,
        )
        return await self._build_timeline(
            organization_id=organization_id,
            phone_e164=phone,
            customer_id=customer.id if customer else None,
            customer_uuid=customer.customer_uuid if customer else None,
            full_name=customer.full_name if customer else None,
            days=days,
            limit=limit,
        )

    async def get_journey_state(
        self,
        *,
        organization_id: int,
        phone_e164: str | None = None,
        customer_id: int | None = None,
    ) -> dict:
        if customer_id:
            timeline = await self.get_by_customer_id(
                customer_id,
                organization_id=organization_id,
                days=14,
                limit=30,
            )
        elif phone_e164:
            timeline = await self.get_by_phone(
                organization_id=organization_id,
                phone_e164=phone_e164,
                days=14,
                limit=30,
            )
        else:
            return {"journey_state": CustomerJourneyState.UNKNOWN.value}

        if timeline is None:
            return {"journey_state": CustomerJourneyState.UNKNOWN.value}

        return {
            "journey_state": timeline.journey_state.value,
            "channels_active": timeline.channels_active,
            "customer_id": timeline.customer_id,
            "phone_e164": timeline.phone_e164,
        }

    async def _build_timeline(
        self,
        *,
        organization_id: int,
        phone_e164: str,
        customer_id: int | None,
        customer_uuid: str | None,
        full_name: str | None,
        days: int,
        limit: int,
    ) -> CustomerTimeline:
        from_ts = datetime.now(UTC) - timedelta(days=days)
        rows = await db_client.list_customer_timeline_entries(
            organization_id=organization_id,
            phone_e164=phone_e164,
            customer_id=customer_id,
            from_ts=from_ts,
            limit=limit,
        )
        entry_dicts = [
            {
                "event_type": r.event_type,
                "channel": r.channel,
                "journey_state": r.journey_state,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
            }
            for r in rows
        ]
        journey = derive_journey_state(entry_dicts)
        channels = active_channels(entry_dicts)

        entries = [
            TimelineEntry(
                id=row.id,
                organization_id=row.organization_id,
                customer_id=row.customer_id,
                phone_e164=row.phone_e164,
                channel=TimelineChannel(row.channel),
                event_type=row.event_type,
                title=row.title,
                summary=row.summary,
                payload=dict(row.payload or {}),
                workflow_run_id=row.workflow_run_id,
                conversation_id=row.conversation_id,
                transaction_id=row.transaction_id,
                correlation_id=row.correlation_id,
                journey_state=(
                    CustomerJourneyState(row.journey_state)
                    if row.journey_state
                    else None
                ),
                occurred_at=row.occurred_at.isoformat() if row.occurred_at else "",
                platform_event_id=row.platform_event_id,
            )
            for row in rows
        ]

        return CustomerTimeline(
            organization_id=organization_id,
            customer_id=customer_id,
            phone_e164=phone_e164,
            customer_uuid=customer_uuid,
            full_name=full_name,
            journey_state=journey,
            entries=entries,
            channels_active=channels,
        )


_service: CustomerTimelineService | None = None


def get_customer_timeline_service() -> CustomerTimelineService:
    global _service
    if _service is None:
        _service = CustomerTimelineService()
    return _service
