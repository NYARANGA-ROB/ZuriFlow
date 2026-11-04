"""Compliance audit logging for debt collection calls."""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from api.constants import (
    CRM_ENABLED,
    DEBT_COLLECTION_COMPLIANCE_AUDIT_TTL_S,
    REDIS_URL,
)
from api.services.debt_collection.analytics import track_compliance_event
from api.services.debt_collection.compliance.types import ComplianceAuditEntry
from api.services.debt_collection.types import DebtCollectionSession


class ComplianceAuditLogger:
    """Append-only audit trail for compliance moderation decisions."""

    def __init__(self, *, max_entries_per_session: int = 500) -> None:
        self._max_entries = max_entries_per_session
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    def _redis_key(self, session_id: str) -> str:
        return f"debt_compliance_audit:{session_id}"

    async def log(
        self,
        session: DebtCollectionSession,
        entry: ComplianceAuditEntry,
    ) -> None:
        payload = entry.to_dict()
        payload["timestamp"] = time.time()

        audit_log: list[dict[str, Any]] = list(
            session.variables.get("compliance_audit") or []
        )
        audit_log.append(payload)
        if len(audit_log) > self._max_entries:
            audit_log = audit_log[-self._max_entries :]
        session.variables["compliance_audit"] = audit_log
        session.variables["compliance_violation_count"] = int(
            session.variables.get("compliance_violation_count", 0)
        ) + len(entry.violations)

        try:
            redis = await self._get_redis()
            key = self._redis_key(session.session_id)
            pipe = redis.pipeline()
            pipe.lpush(key, json.dumps(payload))
            pipe.ltrim(key, 0, self._max_entries - 1)
            pipe.expire(key, DEBT_COLLECTION_COMPLIANCE_AUDIT_TTL_S)
            await pipe.execute()
        except Exception:
            pass

        if entry.violations:
            track_compliance_event(
                organization_id=session.organization_id,
                session_id=session.session_id,
                workflow_run_id=session.workflow_run_id or 0,
                action=entry.action,
                violation_count=len(entry.violations),
                speaker=entry.speaker.value,
                language=session.locale,
                properties={
                    "violations": [v.to_dict() for v in entry.violations],
                    "original_text": entry.original_text[:500],
                    "final_text": entry.final_text[:500],
                },
            )

        await self._maybe_log_crm(session, entry)

    async def _maybe_log_crm(
        self,
        session: DebtCollectionSession,
        entry: ComplianceAuditEntry,
    ) -> None:
        customer_id = session.variables.get("crm_customer_id")
        if not CRM_ENABLED or not customer_id or not entry.violations:
            return
        try:
            from api.services.crm.audit import get_crm_audit_logger

            await get_crm_audit_logger().log(
                organization_id=session.organization_id,
                action="compliance_violation",
                resource_type="debt_collection_session",
                customer_id=int(customer_id),
                resource_id=session.session_id,
                metadata={
                    "violations": [v.to_dict() for v in entry.violations],
                    "speaker": entry.speaker.value,
                    "action": entry.action,
                },
            )
        except Exception:
            pass

    async def list_entries(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            redis = await self._get_redis()
            raw_items = await redis.lrange(self._redis_key(session_id), 0, limit - 1)
            return [json.loads(item) for item in raw_items]
        except Exception:
            return []

    def list_from_session(
        self,
        session: DebtCollectionSession,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        audit_log: list[dict[str, Any]] = list(
            session.variables.get("compliance_audit") or []
        )
        return list(reversed(audit_log[-limit:]))


_audit: ComplianceAuditLogger | None = None


def get_compliance_audit_logger() -> ComplianceAuditLogger:
    global _audit
    if _audit is None:
        _audit = ComplianceAuditLogger()
    return _audit
