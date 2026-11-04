"""Digital Twin application service: health, ingest, approve, sync, tools."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from api.db import db_client
from api.utils.credential_encryption import encrypt_credential_data, decrypt_credential_data
from api.services.business_twin.authority import rank_sources
from api.services.business_twin.cache import EVENT_INVALIDATIONS, invalidate
from api.services.business_twin.calendar import is_open_at, match_branch, now_eat
from api.services.business_twin.change_detection import detect_changes
from api.services.business_twin.conflicts import detect_conflict, resolve_with_authority
from api.services.business_twin.connector_types import DATA_UNAVAILABLE, capabilities_for
from api.services.business_twin.connectors import providers_from_snapshots
from api.services.business_twin.documents import extract_document_payload, validate_upload
from api.services.business_twin.freshness import freshness_score, may_answer_from_knowledge
from api.services.business_twin.interview import extract_from_conversation, next_question
from api.services.business_twin.kenya import KENYA_PUBLIC_HOLIDAYS_2026, template_for
from api.services.business_twin.quality import overall, score_collection, score_profile
from api.services.business_twin.resolver import resolve_information
from api.services.business_twin.rest_connector import invoke_rest_endpoint
from api.services.business_twin.risk import auto_accept_allowed, classify_risk, requires_human_approval
from api.services.business_twin.routing import FALLBACK_MESSAGE, route_query
from api.services.business_twin.webhook_security import redact_question
from api.services.business_twin.website import ingest_website
from api.services.control_plane.audit import log_admin_action
from api.services.kenya.config import KENYA

AUDIT_CREATED = "business_information_created"
AUDIT_MODIFIED = "business_information_modified"
AUDIT_APPROVED = "change_approved"
AUDIT_REJECTED = "change_rejected"
AUDIT_SYNC = "synchronization_executed"
AUDIT_TOOL = "live_tool_executed"
AUDIT_CONFLICT = "conflict_resolved"
AUDIT_SOURCE = "source_connected"


def _serialize_profile(row) -> dict[str, Any]:
    if row is None:
        return {}
    score, status = freshness_score(last_verified_at=row.last_verified_at, expires_at=row.expires_at)
    return {
        "id": row.id,
        "legal_name": row.legal_name,
        "trading_name": row.trading_name,
        "description": row.description,
        "industry": row.industry,
        "sub_industry": row.sub_industry,
        "website": row.website,
        "email": row.email,
        "phones": row.phones_json,
        "counties": row.counties_json,
        "service_areas": row.service_areas_json,
        "languages": row.languages_json,
        "hours": row.hours_json,
        "payment": row.payment_json,
        "operational_refs": row.operational_refs_json,
        "source": row.source,
        "source_type": row.source_type,
        "confidence": row.confidence,
        "status": status if row.status == "verified" else row.status,
        "freshness_score": score,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
        "version": row.version,
        "currency": KENYA.currency_code,
        "timezone": KENYA.timezone,
    }


async def get_or_create_profile(organization_id: int) -> dict[str, Any]:
    row = await db_client.get_business_profile(organization_id)
    if row is None:
        row = await db_client.upsert_business_profile(
            organization_id,
            languages_json=["en", "sw", "mixed"],
            hours_json={"timezone": KENYA.timezone, "weekdays": "08:00-17:00"},
            payment_json={"mpesa_enabled": True, "currency": KENYA.currency_code},
            source="business_admin",
            source_type="business_admin",
            status="pending_review",
            confidence=1.0,
        )
    return _serialize_profile(row)


async def save_profile(
    organization_id: int,
    payload: dict[str, Any],
    *,
    actor_user_id: int | None,
    source: str = "business_admin",
) -> dict[str, Any]:
    mapped = {
        "legal_name": payload.get("legal_name") or payload.get("business_name"),
        "trading_name": payload.get("trading_name"),
        "description": payload.get("description"),
        "industry": payload.get("industry"),
        "sub_industry": payload.get("sub_industry"),
        "website": payload.get("website"),
        "email": payload.get("email"),
        "phones_json": payload.get("phones") or payload.get("phones_json"),
        "counties_json": payload.get("counties") or payload.get("counties_json"),
        "service_areas_json": payload.get("service_areas"),
        "languages_json": payload.get("languages"),
        "hours_json": payload.get("hours") or payload.get("hours_json"),
        "payment_json": payload.get("payment") or payload.get("payment_json"),
        "source": source,
        "source_type": source,
        "last_verified_at": datetime.now(UTC) if source in {"business_admin", "business_owner"} else None,
        "status": "verified" if source in {"business_admin", "business_owner"} else "pending_review",
        "confidence": 1.0 if source in {"business_admin", "business_owner"} else 0.8,
    }
    mapped = {k: v for k, v in mapped.items() if v is not None}
    previous = await db_client.get_business_profile(organization_id)
    row = await db_client.upsert_business_profile(organization_id, **mapped)
    await db_client.add_field_version(
        organization_id,
        entity_type="profile",
        entity_id=row.id,
        field_path="profile",
        value=str(mapped.get("legal_name") or ""),
        version=row.version,
        source=source,
        actor_user_id=actor_user_id,
    )
    await log_admin_action(
        organization_id=organization_id,
        action=AUDIT_MODIFIED if previous else AUDIT_CREATED,
        resource_type="business_profile",
        actor_user_id=actor_user_id,
        resource_id=str(row.id),
        summary="Business information saved",
    )
    return _serialize_profile(row)


async def health_dashboard(organization_id: int) -> dict[str, Any]:
    profile = await get_or_create_profile(organization_id)
    offerings = await db_client.list_offerings(organization_id)
    policies = await db_client.list_policies(organization_id)
    faqs = await db_client.list_faqs(organization_id)
    locations = await db_client.list_locations(organization_id)
    sources = await db_client.list_sources(organization_id)
    changes = await db_client.list_changes(organization_id, status="review_required")
    pending = await db_client.list_changes(organization_id, status="detected")
    conflicts = await db_client.list_conflicts(organization_id)
    alerts = await db_client.list_alerts(organization_id)
    announcements = await db_client.list_announcements(organization_id)
    unanswered = await db_client.list_unanswered(organization_id)
    cats = {
        "profile": score_profile(profile),
        "products": score_collection(offerings),
        "pricing": score_collection([o for o in offerings if o.price_amount is not None]),
        "hours": score_profile({"hours": profile.get("hours"), "last_verified_at": profile.get("last_verified_at"), "legal_name": profile.get("legal_name"), "industry": profile.get("industry"), "languages": profile.get("languages"), "payment": profile.get("payment")}),
        "inventory": {
            "score": 99 if any(s.provider_kind == "inventory" and getattr(s, "lifecycle_state", "") == "active" for s in sources) else 0,
            "completeness": 100 if any(s.provider_kind == "inventory" for s in sources) else 0,
            "freshness": 99 if any(s.provider_kind == "inventory" for s in sources) else 0,
        },
        "policies": score_collection(policies),
    }
    quality_report = overall(cats)
    healthy = [
        s
        for s in sources
        if getattr(s, "lifecycle_state", "active") in {"active", "monitor", "discovered"}
        and getattr(s, "auth_status", "unknown") not in {"failed", "expired"}
    ]
    sections = {
        "profile": {"label": "Business Profile", "state": profile.get("status", "pending_review")},
        "services": {
            "label": "Services",
            "state": "verified" if any(o.kind == "service" for o in offerings) else "pending_review",
        },
        "pricing": {
            "label": "Pricing",
            "state": "review" if changes else "verified",
            "pending": len(changes) + len(pending),
        },
        "hours": {"label": "Opening Hours", "state": "verified" if profile.get("hours") else "pending_review"},
        "inventory": {
            "label": "Inventory",
            "state": "live" if any(s.provider_kind == "inventory" for s in sources) else "not_connected",
        },
        "faqs": {"label": "FAQs", "state": "verified" if faqs else "pending_review"},
        "policies": {"label": "Policies", "state": "verified" if policies else "pending_review"},
        "promotions": {
            "label": "Promotions",
            "state": "expiring" if announcements else "none",
        },
        "locations": {"label": "Locations", "state": "verified" if locations else "pending_review"},
    }
    return {
        "overall_freshness": quality_report["overall"],
        "quality": quality_report,
        "knowledge_health": cats["profile"]["score"],
        "live_data": cats["inventory"]["score"],
        "integrations_healthy": f"{len(healthy)}/{len(sources)}" if sources else "0/0",
        "unanswered_count": len(unanswered),
        "stale_count": sum(1 for v in cats.values() if int(v.get("freshness") or 0) < 70),
        "sections": sections,
        "pending_changes": len(changes) + len(pending),
        "conflicts": len(conflicts),
        "alerts": [
            {"id": a.id, "code": a.code, "title": a.title, "body": a.body, "severity": a.severity}
            for a in alerts
        ],
        "profile": profile,
        "industry_template": template_for(profile.get("industry")),
        "kenya_holidays": [{"date": d, "name": n} for d, n in KENYA_PUBLIC_HOLIDAYS_2026],
    }


async def inbox(organization_id: int) -> dict[str, Any]:
    changes = await db_client.list_changes(organization_id)
    conflicts = await db_client.list_conflicts(organization_id)
    runs = await db_client.list_sync_runs(organization_id)
    failed = [r for r in runs if r.status == "failed"]
    return {
        "changes": [
            {
                "id": c.id,
                "field": c.field_path,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "source": c.source,
                "confidence": c.confidence,
                "risk": c.risk_level,
                "status": c.status,
                "category": getattr(c, "category", None) or _change_category(c.field_path),
                "detected_at": c.detected_at.isoformat() if c.detected_at else None,
            }
            for c in changes
            if c.status in {"detected", "review_required"}
        ],
        "conflicts": [
            {
                "id": row.id,
                "field": row.field_path,
                "source_a": row.source_a,
                "value_a": row.value_a,
                "source_b": row.source_b,
                "value_b": row.value_b,
                "status": row.resolution_status,
            }
            for row in conflicts
        ],
        "failed_syncs": [
            {"id": r.id, "status": r.status, "error": r.error_summary, "started_at": r.started_at.isoformat() if r.started_at else None}
            for r in failed
        ],
    }


async def ingest_website_for_org(organization_id: int, url: str, *, actor_user_id: int | None) -> dict[str, Any]:
    result = await ingest_website(url)
    merged = result["merged"]
    previous = await db_client.get_business_profile(organization_id)
    prev_dump = {"hours": (previous.hours_json if previous else {}), "phones": (previous.phones_json if previous else [])}
    current = {
        "hours": {"mentions": merged.get("hours_mentions")},
        "phones": merged.get("phones"),
        "services": merged.get("services"),
    }
    changes = detect_changes(prev_dump, current, source="website")
    stored = []
    for change in changes:
        risk = classify_risk(change["field_path"], source="website")
        status = "auto_accepted" if auto_accept_allowed(risk, confidence=0.74) else "review_required"
        if requires_human_approval(risk, confidence=0.74):
            status = "review_required"
        row = await db_client.add_change(
            organization_id,
            field_path=change["field_path"],
            old_value=change.get("old_value"),
            new_value=change.get("new_value"),
            source="website",
            confidence=0.74,
            risk_level=risk.value,
            status=status,
            metadata_json={"kind": change["kind"], "url": url},
        )
        stored.append(row.id)
        if status == "review_required":
            await db_client.add_approval(organization_id, change_id=row.id, decision="pending")
    await db_client.upsert_business_profile(
        organization_id,
        website=url,
        phones_json=merged.get("phones") or None,
        source="website",
        source_type="website",
        source_reference=url,
        confidence=0.74,
        status="pending_review",
    )
    for service in merged.get("services") or []:
        await db_client.add_offering(
            organization_id,
            kind="service",
            name=service,
            source="website",
            source_type="website",
            source_reference=url,
            confidence=0.74,
            status="pending_review",
        )
    for faq in merged.get("faqs") or []:
        if faq.get("question"):
            await db_client.add_faq(
                organization_id,
                question=faq["question"],
                answer=faq.get("answer") or "",
                source="website",
                source_type="website",
                confidence=0.7,
                status="pending_review",
            )
    await log_admin_action(
        organization_id=organization_id,
        action="knowledge_imported",
        resource_type="website",
        actor_user_id=actor_user_id,
        summary=f"Imported website {url}",
    )
    return {"ingestion": result, "change_ids": stored}


async def ingest_document_text(
    organization_id: int,
    *,
    filename: str,
    mime_type: str | None,
    text: str,
    size_bytes: int | None,
    actor_user_id: int | None,
) -> dict[str, Any]:
    kind = validate_upload(filename=filename, mime_type=mime_type, size_bytes=size_bytes)
    payload = extract_document_payload(filename=filename, mime_type=mime_type, text=text)
    await db_client.add_source(
        organization_id,
        provider_kind="document",
        adapter_key="upload",
        display_name=filename,
        schedule="manual",
        is_live=False,
        config_json={"kind": kind, "filename": filename},
        status="active",
    )
    await log_admin_action(
        organization_id=organization_id,
        action="knowledge_imported",
        resource_type="document",
        actor_user_id=actor_user_id,
        summary=f"Uploaded {filename}",
    )
    return payload


async def apply_interview(
    organization_id: int, transcript: str, *, actor_user_id: int | None
) -> dict[str, Any]:
    extracted = extract_from_conversation(transcript)
    session = await db_client.add_interview(
        organization_id,
        transcript=transcript,
        extracted_json=extracted,
        status="pending_review",
        created_by_user_id=actor_user_id,
    )
    return {"session_id": session.id, "extracted": extracted, "next_question": next_question(0)}


async def approve_change(
    organization_id: int,
    change_id: int,
    *,
    decision: str,
    reason: str | None,
    actor_user_id: int | None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    change = await db_client.get_change(organization_id, change_id)
    if change is None:
        raise ValueError("Change not found")
    if change.risk_level == "critical" and decision == "approved" and actor_user_id is None:
        raise ValueError("Critical changes require an authorized reviewer")
    new_status = "approved" if decision == "approved" else "rejected"
    await db_client.update_change(organization_id, change_id, status=new_status)
    await db_client.add_approval(
        organization_id,
        change_id=change_id,
        reviewer_user_id=actor_user_id,
        decision=decision,
        reason=reason,
        ip_address=ip_address,
        decided_at=datetime.now(UTC),
    )
    if decision == "approved":
        await db_client.upsert_business_profile(
            organization_id,
            last_verified_at=datetime.now(UTC),
            status="verified",
        )
    await log_admin_action(
        organization_id=organization_id,
        action=AUDIT_APPROVED if decision == "approved" else AUDIT_REJECTED,
        resource_type="business_change",
        actor_user_id=actor_user_id,
        resource_id=str(change_id),
        summary=reason or decision,
    )
    return {"id": change_id, "status": new_status}


async def rollback_field(
    organization_id: int, entity_type: str, entity_id: int, field_path: str, version: int
) -> dict[str, Any]:
    versions = await db_client.list_field_versions(organization_id, entity_type, entity_id, field_path)
    match = next((v for v in versions if v.version == version), None)
    if match is None:
        raise ValueError("Version not found")
    await db_client.add_field_version(
        organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        field_path=field_path,
        value=match.value,
        version=(versions[0].version + 1 if versions else 1),
        source="rollback",
        actor_user_id=None,
    )
    await log_admin_action(
        organization_id=organization_id,
        action="knowledge_rolled_back",
        resource_type=entity_type,
        resource_id=str(entity_id),
        summary=f"Restored {field_path} v{version}",
    )
    return {"restored": match.value, "version": version}


def _change_category(field_path: str) -> str:
    path = (field_path or "").lower()
    if "price" in path or "kes" in path:
        return "pricing"
    if "hour" in path or "open" in path or "close" in path:
        return "hours"
    if "product" in path:
        return "products"
    if "service" in path:
        return "services"
    if "policy" in path:
        return "policies"
    if "location" in path or "branch" in path:
        return "locations"
    if "promo" in path:
        return "promotions"
    if "inventory" in path:
        return "integrations"
    return "all"


async def connect_source(
    organization_id: int,
    *,
    provider_kind: str,
    adapter_key: str,
    display_name: str,
    schedule: str,
    webhook_secret: str | None,
    config: dict[str, Any] | None,
    actor_user_id: int | None,
    allowlisted_hosts: list[str] | None = None,
) -> dict[str, Any]:
    creds = {}
    if webhook_secret:
        creds["webhook_secret"] = webhook_secret
    extra = dict(config or {})
    extra.pop("webhook_secret", None)
    extra.pop("api_key", None)
    extra.pop("password", None)
    extra.pop("token", None)
    if config:
        for secret_key in ("api_key", "password", "token", "bearer"):
            if config.get(secret_key):
                creds[secret_key] = config[secret_key]
    source = await db_client.add_source(
        organization_id,
        provider_kind=provider_kind,
        adapter_key=adapter_key,
        display_name=display_name,
        schedule=schedule,
        webhook_secret=None,
        credentials_json=encrypt_credential_data(creds) if creds else {},
        allowlisted_hosts_json=allowlisted_hosts or extra.get("allowlisted_hosts") or [],
        config_json=extra,
        lifecycle_state="active" if provider_kind in {"crm", "payment", "csv", "webhook"} else "connect",
        auth_status="ok" if provider_kind in {"crm", "payment"} else "unknown",
        is_live=provider_kind in {"inventory", "booking", "payment", "order", "crm", "rest"},
    )
    await db_client.add_sync_job(
        organization_id,
        source_id=source.id,
        schedule=schedule,
        enabled=True,
        next_run_at=datetime.now(UTC),
    )
    await log_admin_action(
        organization_id=organization_id,
        action=AUDIT_SOURCE,
        resource_type="business_source",
        actor_user_id=actor_user_id,
        resource_id=str(source.id),
        summary=display_name,
        metadata={"provider_kind": provider_kind, "has_credentials": bool(creds)},
    )
    return serialize_source(source)


def serialize_source(source) -> dict[str, Any]:
    last_sync = source.last_sync_at or getattr(source, "last_success_at", None)
    attention = None
    lifecycle = getattr(source, "lifecycle_state", None) or source.status
    if getattr(source, "auth_status", None) in {"failed", "expired"}:
        attention = "Authentication failed"
    state_label = "Connected" if lifecycle in {"active", "monitor"} else lifecycle
    healthy = attention is None and lifecycle in {"active", "monitor", "connect"}
    return {
        "id": source.id,
        "provider_kind": source.provider_kind,
        "adapter_key": source.adapter_key,
        "display_name": source.display_name,
        "schedule": source.schedule,
        "status": source.status,
        "lifecycle_state": lifecycle,
        "is_live": source.is_live,
        "capabilities": list(
            capabilities_for(
                source.provider_kind,
                list((source.config_json or {}).get("endpoints") or {}).keys(),
            )
        ),
        "health": {
            "label": "Healthy" if healthy else "Attention required",
            "attention": attention,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "last_failure": getattr(source, "last_failure_at", None).isoformat()
            if getattr(source, "last_failure_at", None)
            else None,
            "latency_ms": getattr(source, "latency_ms", None),
            "error_rate": getattr(source, "error_rate", 0),
            "auth_status": getattr(source, "auth_status", "unknown"),
            "records_synchronized": getattr(source, "records_synced", 0),
        },
        "has_credentials": bool(getattr(source, "credentials_json", None)),
    }


def source_webhook_secret(source) -> str | None:
    blob = decrypt_credential_data(getattr(source, "credentials_json", None) or {})
    return blob.get("webhook_secret") or source.webhook_secret



def verify_webhook_signature(secret: str | None, body: bytes, signature: str | None) -> bool:
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


async def ingest_event(
    organization_id: int,
    source_id: int,
    event_type: str,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    event = await db_client.add_event(
        organization_id,
        event_type=event_type,
        source_id=source_id,
        payload_json=payload,
        correlation_id=correlation_id or str(uuid.uuid4()),
        processed=False,
    )
    kinds = EVENT_INVALIDATIONS.get(event_type, ("profile",))
    await invalidate(organization_id, *kinds)
    await record_snapshot_delta(organization_id, source_id, {event_type: payload})
    return {"event_id": event.id, "correlation_id": event.correlation_id}


async def record_snapshot_delta(
    organization_id: int, source_id: int, current: dict[str, Any]
) -> list[int]:
    previous = await db_client.latest_snapshot(organization_id, source_id)
    prev_payload = previous.payload_json if previous else {}
    await db_client.add_snapshot(
        organization_id, source_id, current, record_count=len(current)
    )
    changes = detect_changes(prev_payload, current, source="webhook")
    ids: list[int] = []
    for change in changes:
        risk = classify_risk(change["field_path"])
        status = "review_required" if requires_human_approval(risk, confidence=1.0) else "detected"
        if auto_accept_allowed(risk, confidence=1.0):
            status = "auto_accepted"
        row = await db_client.add_change(
            organization_id,
            field_path=change["field_path"],
            old_value=change.get("old_value"),
            new_value=change.get("new_value"),
            source="webhook",
            source_id=source_id,
            confidence=1.0,
            risk_level=risk.value,
            status=status,
        )
        ids.append(row.id)
    conflict = detect_conflict(
        "payload",
        {"previous": str(prev_payload)[:200], "current": str(current)[:200]} if prev_payload != current and prev_payload else {},
    )
    if conflict and prev_payload:
        await db_client.add_conflict(organization_id, **{k: v for k, v in conflict.items() if k != "resolution_status"}, resolution_status="open")
    return ids


async def run_sync(organization_id: int, source_id: int, *, correlation_id: str | None = None) -> dict[str, Any]:
    source = await db_client.get_source(organization_id, source_id)
    if source is None:
        raise ValueError("Connected system not found")
    started = datetime.now(UTC)
    run = await db_client.add_sync_run(
        organization_id,
        source_id=source_id,
        status="running",
        correlation_id=correlation_id or str(uuid.uuid4()),
        started_at=started,
    )
    try:
        payload = source.config_json.get("snapshot") or {}
        change_ids = await record_snapshot_delta(organization_id, source_id, payload)
        ended = datetime.now(UTC)
        await db_client.finish_sync_run(
            organization_id,
            run.id,
            status="completed",
            ended_at=ended,
            records_discovered=len(payload),
            records_changed=len(change_ids),
            duration_ms=int((ended - started).total_seconds() * 1000),
        )
        await log_admin_action(
            organization_id=organization_id,
            action=AUDIT_SYNC,
            resource_type="business_source",
            resource_id=str(source_id),
            summary="Sync completed",
            metadata={"correlation_id": run.correlation_id},
        )
        await db_client.update_source(
            organization_id,
            source_id,
            last_success_at=ended,
            last_sync_at=ended,
            latency_ms=int((ended - started).total_seconds() * 1000),
            records_synced=len(payload),
            lifecycle_state="active",
            auth_status="ok",
        )
        return {"run_id": run.id, "changes": len(change_ids), "correlation_id": run.correlation_id}
    except Exception as exc:
        logger.exception("Business sync failed")
        await db_client.finish_sync_run(
            organization_id,
            run.id,
            status="failed",
            ended_at=datetime.now(UTC),
            error_summary=str(exc),
            records_failed=1,
        )
        await db_client.add_sync_error(
            organization_id, run_id=run.id, message=str(exc), detail_json={}
        )
        await db_client.add_alert(
            organization_id,
            code="sync_failed",
            title="A connected system failed to update",
            body="Inventory or booking sync needs attention.",
            severity="warning",
            action_url="/business/changes",
        )
        await db_client.update_source(
            organization_id,
            source_id,
            last_failure_at=datetime.now(UTC),
            last_failure_message=str(exc)[:500],
        )
        raise


async def execute_tool(
    organization_id: int,
    tool: str,
    arguments: dict[str, Any],
    *,
    actor: str = "agent",
) -> dict[str, Any]:
    profile = await get_or_create_profile(organization_id)
    sources = await db_client.list_sources(organization_id)
    inventory_map: dict = {}
    booking_map: dict = {}
    order_map: dict = {}
    for source in sources:
        snap = await db_client.latest_snapshot(organization_id, source.id)
        if not snap:
            continue
        if source.provider_kind == "inventory":
            inventory_map.update(snap.payload_json.get("items") or snap.payload_json)
        if source.provider_kind == "booking":
            booking_map.update(snap.payload_json.get("slots") or snap.payload_json)
        if source.provider_kind == "order":
            order_map.update(snap.payload_json.get("orders") or snap.payload_json)
    providers = providers_from_snapshots(inventory_map, booking_map, order_map)
    result: dict[str, Any]
    if tool == "get_business_profile":
        result = {"plane": "knowledge", **profile}
    elif tool == "get_business_hours":
        locations = await db_client.list_locations(organization_id)
        query = arguments.get("query") or arguments.get("branch") or ""
        branch = match_branch(locations, query)
        hours = (branch.hours_json if branch and branch.hours_json else None) or profile.get("hours") or {}
        announcements = await db_client.list_announcements(organization_id)
        now = now_eat()
        closed_by_announcement = False
        for ad in announcements:
            if ad.starts_at and ad.starts_at > now:
                continue
            if ad.ends_at and ad.ends_at < now:
                continue
            if "closed" in (ad.body or "").lower() or "closed" in (ad.title or "").lower():
                if branch and ad.location_id and ad.location_id != branch.id:
                    continue
                closed_by_announcement = True
        target = now
        if "tomorrow" in query.lower():
            from datetime import timedelta

            target = now + timedelta(days=1)
        openness = is_open_at(
            hours_json=hours,
            day=target,
            announcement_closed=closed_by_announcement,
        )
        score = float(profile.get("freshness_score") or 0)
        if not may_answer_from_knowledge(
            status=str(profile.get("status")), risk_level="high", score=score
        ) and profile.get("status") in {"expired", "conflicting", "stale"}:
            result = {"plane": "knowledge", "verified": False, "message": FALLBACK_MESSAGE}
        else:
            result = {
                "plane": "knowledge",
                "hours": hours,
                "branch": branch.name if branch else None,
                "openness": openness,
                "timezone": KENYA.timezone,
                "verified": True,
            }
    elif tool == "get_branch_information":
        locations = await db_client.list_locations(organization_id)
        result = {
            "plane": "knowledge",
            "branches": [{"name": loc.name, "county": loc.county, "address": loc.address} for loc in locations],
        }
    elif tool == "get_service":
        items = await db_client.list_offerings(organization_id, kind="service")
        result = {
            "plane": "knowledge",
            "services": [{"name": i.name, "description": i.description} for i in items],
        }
    elif tool == "get_product":
        items = await db_client.list_offerings(organization_id, kind="product")
        result = {"plane": "knowledge", "products": [{"name": i.name, "sku": i.sku} for i in items]}
    elif tool == "get_price":
        query = (arguments.get("name") or arguments.get("query") or "").lower()
        items = await db_client.list_offerings(organization_id)
        match = next((i for i in items if query and query in (i.name or "").lower()), None)
        if match and match.is_live_priced:
            result = {
                "plane": "live",
                "verified": False,
                "message": FALLBACK_MESSAGE,
            }
        elif match and match.status in {"expired", "conflicting"}:
            result = {"plane": "knowledge", "verified": False, "message": FALLBACK_MESSAGE}
        elif match:
            result = {
                "plane": "knowledge",
                "amount": match.price_amount,
                "currency": match.price_currency,
                "name": match.name,
                "verified": match.status == "verified",
            }
        else:
            result = {"plane": "knowledge", "verified": False, "message": FALLBACK_MESSAGE}
    elif tool == "check_inventory":
        result = await providers["inventory"].check_inventory(
            arguments.get("sku") or arguments.get("product") or "",
            organization_id=organization_id,
        )
    elif tool == "check_appointment_availability":
        result = await providers["booking"].check_availability(
            arguments.get("when") or arguments.get("datetime") or "",
            organization_id=organization_id,
            branch=arguments.get("branch"),
        )
    elif tool == "get_order_status":
        result = await providers["order"].get_order(
            arguments.get("order_id") or "",
            organization_id=organization_id,
        )
    elif tool == "get_delivery_status":
        result = await providers["order"].get_order(
            arguments.get("tracking_id") or arguments.get("order_id") or "",
            organization_id=organization_id,
        )
    elif tool == "get_payment_status":
        result = await providers["payment"].get_payment_status(
            arguments.get("reference") or "",
            organization_id=organization_id,
        )
    elif tool == "get_business_policy":
        policies = await db_client.list_policies(organization_id)
        result = {
            "plane": "knowledge",
            "policies": [{"title": p.title, "body": p.body[:1500]} for p in policies],
        }
    elif tool == "get_current_promotions":
        now = now_eat()
        promos = await db_client.list_promotions(organization_id)
        active = []
        for promo in promos:
            if promo.starts_at and promo.starts_at > now:
                continue
            if promo.ends_at and promo.ends_at < now:
                continue
            if promo.promotion_status != "active":
                continue
            active.append(
                {
                    "name": promo.name,
                    "description": promo.description,
                    "discount": promo.discount,
                    "applicable": promo.applicable,
                }
            )
        ads = await db_client.list_announcements(organization_id)
        for ad in ads:
            if ad.starts_at and ad.starts_at > now:
                continue
            if ad.ends_at and ad.ends_at < now:
                continue
            active.append({"name": ad.title, "description": ad.body})
        result = {"plane": "knowledge", "promotions": active, "verified": True}
    elif tool.startswith("rest:"):
        result = {**DATA_UNAVAILABLE, "reason": "use_named_capability"}
    else:
        result = {"error": "unknown_tool", "message": FALLBACK_MESSAGE}

    rest_sources = [s for s in sources if s.provider_kind == "rest"]
    capability_map = {
        "check_inventory": "inventory_lookup",
        "get_price": "price_lookup",
        "get_product": "product_lookup",
        "check_appointment_availability": "availability",
        "get_order_status": "order_lookup",
        "get_delivery_status": "delivery_status",
        "get_payment_status": "payment_status",
    }
    cap = capability_map.get(tool)
    if cap and rest_sources and (not result.get("verified") or result.get("in_stock") is None):
        for source in rest_sources:
            endpoints = (source.config_json or {}).get("endpoints") or {}
            if cap not in endpoints:
                continue
            hosts = list(getattr(source, "allowlisted_hosts_json", None) or [])
            host = (source.config_json or {}).get("host")
            if host and host not in hosts:
                hosts.append(host)
            creds = decrypt_credential_data(getattr(source, "credentials_json", None) or {})
            headers = {}
            if creds.get("bearer"):
                headers["Authorization"] = f"Bearer {creds['bearer']}"
            try:
                rest_result = await invoke_rest_endpoint(
                    host=host or (hosts[0] if hosts else ""),
                    hosts=hosts,
                    endpoint=endpoints[cap],
                    arguments=arguments,
                    headers=headers,
                )
            except Exception:
                rest_result = {"code": "DATA_UNAVAILABLE", "verified": False}
            if rest_result.get("verified"):
                result = rest_result
                break
            if rest_result.get("code") == "DATA_UNAVAILABLE":
                result = rest_result

    if not result.get("verified") and actor == "agent":
        query = arguments.get("query") or ""
        if query:
            resolution = resolve_information(query)
            await db_client.bump_unanswered(
                organization_id,
                redact_question(query),
                resolution.intent,
                resolution.tool,
            )
    resolution = resolve_information(arguments.get("query") or tool)
    await db_client.add_trace(
        organization_id,
        question=redact_question(str(arguments.get("query") or tool)),
        intent=resolution.intent,
        source_selected=resolution.source,
        authority=resolution.authority,
        freshness=float(profile.get("freshness_score") or 0),
        tool_used=tool,
        confidence=resolution.confidence,
        result_summary=str(result.get("code") or result.get("verified"))[:200],
        reason=resolution.reason,
    )
    await db_client.append_security_audit_event(
        action=AUDIT_TOOL,
        resource_type="business_tool",
        organization_id=organization_id,
        resource_id=tool,
        summary=tool,
        metadata_json={"actor": actor, "args_keys": sorted(arguments.keys())},
    )
    return result


async def route_and_execute(organization_id: int, query: str) -> dict[str, Any]:
    resolution = resolve_information(query)
    result = await execute_tool(organization_id, resolution.tool, {"query": query})
    return {
        "tool": resolution.tool,
        "plane": resolution.plane,
        "intent": resolution.intent,
        "source": resolution.source,
        "authority": resolution.authority,
        "reason": resolution.reason,
        "result": result,
    }


def default_authority(data_type: str) -> list[str]:
    return rank_sources(data_type)
