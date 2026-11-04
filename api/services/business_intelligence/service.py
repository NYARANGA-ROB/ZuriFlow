"""Business intelligence facade: classify, aggregate, insight, dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from api.constants import BUSINESS_INTELLIGENCE_ENABLED
from api.db import db_client
from api.services.business_intelligence.aggregator import aggregate_intelligence
from api.services.business_intelligence.classifier import classify_conversation
from api.services.business_intelligence.dashboards import DASHBOARDS, compose_dashboard
from api.services.business_intelligence.insights import build_insights
from api.services.kenya.analytics import get_kenya_analytics
from api.services.tenant.types import Permission, TenantContext


def _text_from_run(run: Any) -> str:
    ctx = run.gathered_context or {}
    extra = getattr(run, "extra", None) or {}
    for source in (ctx, extra):
        if not isinstance(source, dict):
            continue
        for key in ("transcript", "conversation_text", "summary"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value[:4000]
        messages = source.get("messages")
        if isinstance(messages, list):
            parts: list[str] = []
            for message in messages[-20:]:
                if isinstance(message, dict):
                    parts.append(str(message.get("content") or message.get("text") or ""))
                else:
                    parts.append(str(message))
            blob = " ".join(parts).strip()
            if blob:
                return blob[:4000]
    return ""


class BusinessIntelligenceService:
    @property
    def enabled(self) -> bool:
        return BUSINESS_INTELLIGENCE_ENABLED

    def capabilities(self, ctx: TenantContext | None) -> dict[str, Any]:
        include_payments = bool(ctx and ctx.has_permission(Permission.PAYMENT_ANALYTICS_READ))
        include_excerpts = bool(ctx and ctx.has_permission(Permission.CONVERSATION_PII_READ))
        return {
            "enabled": self.enabled,
            "payments": include_payments,
            "conversation_excerpts": include_excerpts,
            "dashboards": list(DASHBOARDS),
        }

    async def classify_and_store(
        self,
        organization_id: int,
        *,
        text: str,
        workflow_run_id: int | None = None,
        context: dict[str, Any] | None = None,
        transferred: bool = False,
        completed: bool = False,
        county: str | None = None,
    ) -> dict[str, Any]:
        result = classify_conversation(
            text,
            context=context,
            transferred=transferred,
            completed=completed,
            county=county,
        )
        payload = result.to_dict()
        await db_client.upsert_conversation_intelligence(
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            payload=payload,
        )
        return payload

    async def _channel_rates(self, organization_id: int, days: int) -> dict[str, Any]:
        try:
            snapshot = await db_client.engagement_metrics(
                organization_id=organization_id, days=days
            )
        except Exception:
            return {}
        by_channel = {row.get("channel"): row for row in snapshot.get("by_channel") or []}
        sms = by_channel.get("sms") or {}
        whatsapp = by_channel.get("whatsapp") or {}
        return {
            "sms_followup_rate": float(sms.get("delivery_rate") or 0),
            "whatsapp_followup_rate": float(whatsapp.get("delivery_rate") or 0),
        }

    async def snapshot(
        self,
        organization_id: int,
        *,
        days: int = 7,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        start = now - timedelta(days=days)
        prev_start = start - timedelta(days=days)
        call_stats = await db_client.call_volume_stats(
            organization_id, from_dt=start, to_dt=now
        )
        payment_stats = await db_client.payment_volume_stats(
            organization_id, from_dt=start, to_dt=now
        )
        previous_payments = await db_client.payment_volume_stats(
            organization_id, from_dt=prev_start, to_dt=start
        )
        stored = await db_client.list_conversation_intelligence(
            organization_id, from_dt=start, to_dt=now
        )
        classifications = [
            {
                "category": row.category,
                "intent": row.intent,
                "sentiment": row.sentiment,
                "outcome": row.outcome,
                "unresolved_issue": row.unresolved_issue,
                "requested_product": row.requested_product,
                "next_action": row.next_action,
                "language": row.language,
                "code_switched": bool((row.metadata_json or {}).get("code_switched")),
                "contained": row.contained,
                "transferred": row.transferred,
                "first_contact_resolved": row.first_contact_resolved,
                "redacted_excerpt": row.redacted_excerpt,
                "county": row.county,
            }
            for row in stored
        ]
        if not classifications:
            runs = await db_client.list_runs_for_classification(
                organization_id, from_dt=start, to_dt=now
            )
            for run in runs:
                text = _text_from_run(run)
                if not text:
                    continue
                extra = run.extra if isinstance(run.extra, dict) else {}
                transferred = bool(extra.get("transferred") or extra.get("human_transfer"))
                await self.classify_and_store(
                    organization_id,
                    text=text,
                    workflow_run_id=run.id,
                    context={"intent": extra.get("intent")},
                    transferred=transferred,
                    completed=bool(run.is_completed),
                    county=extra.get("county") if isinstance(extra.get("county"), str) else None,
                )
            stored = await db_client.list_conversation_intelligence(
                organization_id, from_dt=start, to_dt=now
            )
            classifications = [
                {
                    "category": row.category,
                    "intent": row.intent,
                    "sentiment": row.sentiment,
                    "outcome": row.outcome,
                    "unresolved_issue": row.unresolved_issue,
                    "requested_product": row.requested_product,
                    "next_action": row.next_action,
                    "language": row.language,
                    "code_switched": bool((row.metadata_json or {}).get("code_switched")),
                    "contained": row.contained,
                    "transferred": row.transferred,
                    "first_contact_resolved": row.first_contact_resolved,
                    "redacted_excerpt": row.redacted_excerpt,
                    "county": row.county,
                }
                for row in stored
            ]
        kenya = {}
        try:
            kenya = get_kenya_analytics().snapshot(organization_id)
        except Exception:
            kenya = {}
        channels = await self._channel_rates(organization_id, days)
        return aggregate_intelligence(
            call_stats=call_stats,
            payment_stats=payment_stats,
            classifications=classifications,
            kenya=kenya,
            channels=channels,
            previous_payments=previous_payments,
        )

    async def dashboard(
        self,
        organization_id: int,
        name: str,
        *,
        days: int = 7,
        ctx: TenantContext | None = None,
    ) -> dict[str, Any]:
        caps = self.capabilities(ctx)
        snap = await self.snapshot(organization_id, days=days)
        insights = build_insights(snap)
        conversations = None
        if name == "conversation":
            rows = await db_client.list_conversation_intelligence(
                organization_id, limit=50
            )
            conversations = [
                {
                    "id": row.id,
                    "category": row.category,
                    "intent": row.intent,
                    "sentiment": row.sentiment,
                    "outcome": row.outcome,
                    "unresolved_issue": row.unresolved_issue,
                    "requested_product": row.requested_product,
                    "next_action": row.next_action,
                    "language": row.language,
                    "redacted_excerpt": row.redacted_excerpt,
                }
                for row in rows
            ]
        return compose_dashboard(
            name,
            snap,
            insights,
            include_payments=caps["payments"],
            include_excerpts=caps["conversation_excerpts"],
            conversations=conversations,
        )


_service: BusinessIntelligenceService | None = None


def get_business_intelligence_service() -> BusinessIntelligenceService:
    global _service
    if _service is None:
        _service = BusinessIntelligenceService()
    return _service
