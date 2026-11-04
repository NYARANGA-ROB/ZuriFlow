"""Context transfer — assemble conversation summaries for human handoff."""

from __future__ import annotations

from typing import Any

from loguru import logger

from api.services.human_escalation.types import HandoffPackage


class ContextTransferSystem:
    """Build handoff packages from memory, workflow runs, and CRM."""

    async def build_handoff(
        self,
        *,
        session_id: str,
        organization_id: int,
        reason: str,
        intent: str = "escalation",
        language: str = "mixed",
        workflow_run_id: int = 0,
        phone_e164: str = "",
        customer_name: str = "",
        call_sid: str = "",
        queue_name: str = "",
        priority: int = 50,
        risk_level: str = "medium",
        extra_context: str = "",
    ) -> HandoffPackage:
        summary_parts: list[str] = []
        transcript: list[dict[str, Any]] = []
        slots: dict[str, str] = {}
        customer_id: int | None = None

        memory_summary = self._from_conversation_memory(session_id)
        if memory_summary:
            summary_parts.append(memory_summary["summary"])
            transcript.extend(memory_summary.get("turns", []))
            slots.update(memory_summary.get("slots", {}))

        if workflow_run_id:
            run_data = await self._from_workflow_run(workflow_run_id)
            if run_data:
                if run_data.get("summary"):
                    summary_parts.append(run_data["summary"])
                transcript.extend(run_data.get("turns", []))
                slots.update(run_data.get("slots", {}))
                customer_id = run_data.get("customer_id")
                if not phone_e164:
                    phone_e164 = run_data.get("phone_e164", "")
                if not customer_name:
                    customer_name = run_data.get("customer_name", "")
                if not call_sid:
                    call_sid = run_data.get("call_sid", "")

        if extra_context:
            summary_parts.append(extra_context)

        if reason and not any(reason in p for p in summary_parts):
            summary_parts.insert(0, f"Reason: {reason}")

        kenya = _kenya_handoff_metadata(session_id)
        if kenya.get("conversation_summary"):
            summary_parts.append(kenya["conversation_summary"])
        slots.update(kenya.get("entities") or {})

        summary = " | ".join(p for p in summary_parts if p) or f"Escalation: {reason}"

        return HandoffPackage(
            session_id=session_id,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            phone_e164=phone_e164,
            customer_name=customer_name,
            customer_id=customer_id,
            intent=intent,
            reason=reason,
            language=kenya.get("detected_language") or language,
            summary=summary[:4000],
            transcript_excerpt=transcript[-8:],
            slots=slots,
            priority=priority,
            risk_level=risk_level,
            call_sid=call_sid,
            queue_name=queue_name,
            metadata=kenya,
        )

    def _from_conversation_memory(self, session_id: str) -> dict[str, Any] | None:
        try:
            from api.services.realtime_conversation_memory import get_conversation_memory_service

            svc = get_conversation_memory_service()
            if not svc.enabled:
                return None
            mgr = svc.session(session_id)
            snap = mgr.snapshot()
            return {
                "summary": snap.summary,
                "turns": [t.to_dict() for t in snap.turns[-6:]],
                "slots": dict(snap.intent.slots),
            }
        except Exception:
            logger.debug("conversation memory unavailable for session {}", session_id)
            return None

    async def _from_workflow_run(self, workflow_run_id: int) -> dict[str, Any] | None:
        try:
            from api.db import db_client

            run = await db_client.get_workflow_run_by_id(workflow_run_id)
            if not run:
                return None

            initial = run.initial_context or {}
            gathered = run.gathered_context or {}
            memory = gathered.get("conversation_memory") or {}

            turns: list[dict[str, Any]] = []
            for turn in memory.get("turns", [])[-6:]:
                if isinstance(turn, dict):
                    turns.append(turn)

            summary = memory.get("summary") or gathered.get("call_summary") or ""
            customer_id = initial.get("customer_id")
            if customer_id is not None:
                try:
                    customer_id = int(customer_id)
                except (TypeError, ValueError):
                    customer_id = None

            return {
                "summary": str(summary) if summary else "",
                "turns": turns,
                "slots": dict(memory.get("slots") or {}),
                "customer_id": customer_id,
                "phone_e164": initial.get("called_number") or initial.get("phone_e164", ""),
                "customer_name": initial.get("customer_name", ""),
                "call_sid": gathered.get("call_id") or gathered.get("call_sid", ""),
            }
        except Exception:
            logger.exception("failed to load workflow run context run={}", workflow_run_id)
            return None


def _kenya_handoff_metadata(session_id: str) -> dict[str, Any]:
    try:
        from api.services.kenya.session import get_kenya_session_store

        snap = get_kenya_session_store().get(session_id).snapshot()
        return {
            "detected_language": snap.get("preferred_language"),
            "conversation_summary": " | ".join(
                get_kenya_session_store().get(session_id).raw_turns[-6:]
            ),
            "customer_intent": (snap.get("last_intents") or ["unknown"])[-1],
            "entities": snap.get("last_entities") or {},
            "previous_attempts": {
                "clarifications": snap.get("clarification_count"),
                "failed_recognition": snap.get("failed_recognition_count"),
                "intents": snap.get("last_intents"),
            },
            "workflow_state": {"style": snap.get("style")},
            "code_switches": snap.get("switch_count"),
        }
    except Exception:
        return {}

