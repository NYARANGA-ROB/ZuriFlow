"""Payment analytics aggregation (M-Pesa and usage)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.db import db_client


def _window(from_ts: float | None, to_ts: float | None, *, days: int = 7):
    import time

    now = time.time()
    end = to_ts if to_ts is not None else now
    start = from_ts if from_ts is not None else end - days * 86400
    return (
        datetime.fromtimestamp(start, tz=timezone.utc),
        datetime.fromtimestamp(end, tz=timezone.utc),
        start,
        end,
    )


class PaymentsAggregator:
    async def summary(
        self,
        organization_id: int,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        start_dt, end_dt, start, end = _window(from_ts, to_ts, days=days)
        mpesa = await db_client.get_mpesa_payment_summary(
            organization_id, from_ts=start_dt, to_ts=end_dt
        )
        usage = await db_client.get_current_usage(organization_id)
        return {
            "organization_id": organization_id,
            "from_ts": start,
            "to_ts": end,
            "mpesa": mpesa,
            "usage_cycle": usage,
        }

    async def search(
        self,
        organization_id: int,
        *,
        q: str | None = None,
        status: str | None = None,
        from_ts: float | None = None,
        to_ts: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        start_dt, end_dt, start, end = _window(from_ts, to_ts)
        rows, total = await db_client.search_mpesa_transactions(
            organization_id,
            q=q,
            status=status,
            from_ts=start_dt,
            to_ts=end_dt,
            limit=limit,
            offset=offset,
        )
        return {
            "organization_id": organization_id,
            "from_ts": start,
            "to_ts": end,
            "total": total,
            "limit": limit,
            "offset": offset,
            "transactions": [
                {
                    "id": tx.id,
                    "status": tx.status,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "phone_e164": tx.phone_e164,
                    "account_reference": tx.account_reference,
                    "workflow_run_id": tx.workflow_run_id,
                    "mpesa_receipt_number": tx.mpesa_receipt_number,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                }
                for tx in rows
            ],
        }
