from __future__ import annotations

from typing import Any

from api.constants import REALTIME_MEMORY_ENABLED
from api.services.realtime_conversation_memory.config import DEFAULT_MEMORY_CONFIG
from api.services.realtime_conversation_memory.intent import IntentTracker
from api.services.realtime_conversation_memory.summarizer import ContextSummarizer
from api.services.realtime_conversation_memory.types import CallIntent, IntentState, TurnRecord
from api.services.whatsapp.post_call.config import PostCallWorkflowConfig
from api.services.whatsapp.post_call.types import PostCallSummary
from api.services.whatsapp.templates.i18n import detect_language
from api.utils.telephony_address import normalize_telephony_address


class PostCallSummaryGenerator:
    """Build a multilingual post-call summary from memory, transcript, or context."""

    def __init__(self) -> None:
        self._summarizer = ContextSummarizer(DEFAULT_MEMORY_CONFIG)
        self._intent_tracker = IntentTracker(DEFAULT_MEMORY_CONFIG)

    def generate(
        self,
        *,
        workflow_run: Any,
        config: PostCallWorkflowConfig,
        memory_snapshot: dict[str, Any] | None = None,
    ) -> PostCallSummary:
        gathered = workflow_run.gathered_context or {}
        initial = workflow_run.initial_context or {}
        logs = workflow_run.logs or {}

        snapshot = memory_snapshot or gathered.get("conversation_memory") or gathered.get(
            "memory_snapshot"
        )
        if snapshot:
            return self._from_memory_snapshot(snapshot, config, source="memory")

        live_snapshot = self._try_live_memory(gathered, config)
        if live_snapshot:
            return live_snapshot

        transcript_summary = self._from_transcript_logs(logs, config)
        if transcript_summary:
            return transcript_summary

        return self._from_gathered_context(gathered, initial, config)

    def _try_live_memory(
        self,
        gathered: dict[str, Any],
        config: PostCallWorkflowConfig,
    ) -> PostCallSummary | None:
        if not REALTIME_MEMORY_ENABLED:
            return None
        session_id = gathered.get("memory_session_id") or gathered.get("session_id")
        if not session_id:
            return None
        try:
            from api.services.realtime_conversation_memory.service import (
                get_conversation_memory_service,
            )

            svc = get_conversation_memory_service()
            snap = svc.end_session(str(session_id))
            if snap is None:
                return None
            return self._from_memory_snapshot(snap.to_dict(), config, source="live_memory")
        except Exception:
            return None

    def _from_memory_snapshot(
        self,
        snapshot: dict[str, Any],
        config: PostCallWorkflowConfig,
        *,
        source: str,
    ) -> PostCallSummary:
        intent_data = snapshot.get("intent") or {}
        if isinstance(intent_data, str):
            intent = intent_data
            confidence = float(snapshot.get("intent_confidence", 0.0))
            slots: dict[str, str] = dict(snapshot.get("slots") or {})
        else:
            intent = intent_data.get("current", "unknown")
            confidence = float(intent_data.get("confidence", 0.0))
            slots = dict(intent_data.get("slots") or {})

        summary_text = str(snapshot.get("summary") or "").strip()
        if not summary_text:
            turns = self._turns_from_snapshot(snapshot)
            intent_state = IntentState(
                current=CallIntent(intent) if intent in CallIntent._value2member_map_ else CallIntent.UNKNOWN,
                confidence=confidence,
                slots=slots,
            )
            summary_text = self._summarizer.summarize(
                turns,
                intent_state,
                interrupted=bool(snapshot.get("interrupted")),
                partial_assistant=str(snapshot.get("partial_assistant") or ""),
            )

        language = self._resolve_language(summary_text, gathered_language=None, config=config)
        next_steps = self._derive_next_steps(intent, slots, language)
        return PostCallSummary(
            text=summary_text or self._default_summary(language),
            intent=str(intent),
            intent_confidence=confidence,
            next_steps=next_steps,
            language=language,
            slots=slots,
            source=source,
        )

    def _from_transcript_logs(
        self,
        logs: dict[str, Any],
        config: PostCallWorkflowConfig,
    ) -> PostCallSummary | None:
        events = logs.get("realtime_feedback_events") or logs.get("transcript_events") or []
        if not events:
            return None

        turns: list[TurnRecord] = []
        turn_id = 0
        pending_user = ""
        for event in events:
            role = (event.get("role") or event.get("speaker") or "").lower()
            text = str(event.get("text") or event.get("content") or "").strip()
            if not text:
                continue
            if role in ("user", "caller"):
                pending_user = text
            elif role in ("assistant", "agent", "bot") and pending_user:
                turns.append(
                    TurnRecord(
                        turn_id=turn_id,
                        user_text=pending_user,
                        assistant_text=text,
                    )
                )
                turn_id += 1
                pending_user = ""

        if not turns and not pending_user:
            return None

        intent_state = IntentState()
        for turn in turns[-3:]:
            intent_state = self._intent_tracker.update(turn.user_text, intent_state)

        summary_text = self._summarizer.summarize(turns, intent_state)
        language = self._resolve_language(summary_text, gathered_language=None, config=config)
        return PostCallSummary(
            text=summary_text or self._default_summary(language),
            intent=intent_state.current.value,
            intent_confidence=intent_state.confidence,
            next_steps=self._derive_next_steps(
                intent_state.current.value, intent_state.slots, language
            ),
            language=language,
            slots=dict(intent_state.slots),
            source="transcript",
        )

    def _from_gathered_context(
        self,
        gathered: dict[str, Any],
        initial: dict[str, Any],
        config: PostCallWorkflowConfig,
    ) -> PostCallSummary:
        summary_text = str(
            gathered.get("call_summary")
            or gathered.get("summary")
            or initial.get("call_summary")
            or ""
        ).strip()
        intent = str(gathered.get("intent") or initial.get("intent") or "unknown")
        confidence = float(gathered.get("intent_confidence", 0.0))
        slots = {
            k: str(v)
            for k, v in (gathered.get("slots") or initial.get("slots") or {}).items()
            if v
        }
        language = self._resolve_language(
            summary_text,
            gathered_language=gathered.get("language") or initial.get("language"),
            config=config,
        )
        next_steps = str(
            gathered.get("next_steps") or initial.get("next_steps") or ""
        ) or self._derive_next_steps(intent, slots, language)
        return PostCallSummary(
            text=summary_text or self._default_summary(language),
            intent=intent,
            intent_confidence=confidence,
            next_steps=next_steps,
            language=language,
            slots=slots,
            source="context",
        )

    @staticmethod
    def _turns_from_snapshot(snapshot: dict[str, Any]) -> list[TurnRecord]:
        turns: list[TurnRecord] = []
        for idx, item in enumerate(snapshot.get("turns") or []):
            turns.append(
                TurnRecord(
                    turn_id=item.get("turn_id", idx),
                    user_text=str(item.get("user") or ""),
                    assistant_text=str(item.get("assistant") or ""),
                )
            )
        return turns

    @staticmethod
    def _resolve_language(
        summary_text: str,
        *,
        gathered_language: str | None,
        config: PostCallWorkflowConfig,
    ) -> str:
        if gathered_language in ("en", "sw", "mixed"):
            return gathered_language
        if config.default_language in ("en", "sw", "mixed"):
            detected = detect_language(summary_text, config.default_language)
            return detected
        return detect_language(summary_text, "en")

    @staticmethod
    def _derive_next_steps(intent: str, slots: dict[str, str], language: str) -> str:
        if language == "sw":
            if intent == "request_payment":
                return "Tumia kiungo cha malipo kilichotumwa."
            if intent in ("request_support", "account_inquiry"):
                return "Mteja anaweza kuhitaji msaada wa ziada."
            return "Wasiliana nasi ikiwa unahitaji msaada zaidi."
        if intent == "request_payment":
            return "Use the payment link we sent."
        if intent in ("request_support", "account_inquiry"):
            return "A team member may follow up if needed."
        return "Reach out if you need anything else."

    @staticmethod
    def _default_summary(language: str) -> str:
        if language == "sw":
            return "Asante kwa simu yako."
        if language == "mixed":
            return "Thanks / asante for your call."
        return "Thanks for your call."


def extract_customer_phone(workflow_run: Any) -> str | None:
    gathered = workflow_run.gathered_context or {}
    initial = workflow_run.initial_context or {}
    for key in (
        "whatsapp_phone",
        "phone_number",
        "customer_phone",
        "to_number",
        "from_number",
    ):
        value = gathered.get(key) or initial.get(key)
        if value:
            return normalize_telephony_address(str(value)).canonical

    direction = str(initial.get("direction") or gathered.get("direction") or "outbound")
    if direction == "inbound":
        phone = gathered.get("from_number") or initial.get("from_number")
    else:
        phone = gathered.get("to_number") or initial.get("to_number")
    if phone:
        return normalize_telephony_address(str(phone)).canonical
    return None


def extract_customer_name(workflow_run: Any) -> str:
    gathered = workflow_run.gathered_context or {}
    initial = workflow_run.initial_context or {}
    for key in ("customer_name", "name", "caller_name"):
        value = gathered.get(key) or initial.get(key)
        if value:
            return str(value)
    return "there"
