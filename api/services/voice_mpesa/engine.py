from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from api.db import db_client
from api.services.mpesa_daraja.config import ORG_CONFIG_KEY
from api.services.mpesa_daraja.pipeline import STKPushService
from api.services.org_config_cache import mpesa_config_cache
from api.services.mpesa_daraja.types import (
    MpesaEventType,
    MpesaTransactionStatus,
    STKPushRequest,
)
from api.services.realtime_conversation_memory.types import CallIntent
from api.services.voice_mpesa.config import VoiceMpesaConfig
from api.services.voice_mpesa.confirmation import VoicePaymentConfirmation
from api.services.voice_mpesa.recovery import VoicePaymentRecovery
from api.services.voice_mpesa.receipt import VoiceMpesaReceiptSender
from api.services.voice_mpesa.state_machine import VoicePaymentStateMachine
from api.services.voice_mpesa.types import (
    TERMINAL_STATES,
    VoicePaymentEvent,
    VoicePaymentSession,
    VoicePaymentState,
    VoicePaymentTurnResult,
)
from api.tasks.function_names import FunctionNames
from api.utils.telephony_address import normalize_telephony_address


class VoiceMpesaWorkflowEngine:
    """Orchestrate voice-driven M-Pesa payment during realtime calls."""

    def __init__(self) -> None:
        self._sessions: dict[str, VoicePaymentSession] = {}
        self._state_machine = VoicePaymentStateMachine()
        self._confirmation = VoicePaymentConfirmation()
        self._recovery = VoicePaymentRecovery()
        self._receipts = VoiceMpesaReceiptSender()
        self._stk = STKPushService()
        self._watchers: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def get_session(self, session_id: str) -> VoicePaymentSession | None:
        return self._sessions.get(session_id)

    def consume_pending_prompt(self, session_id: str) -> str | None:
        session = self._sessions.get(session_id)
        if not session or not session.pending_voice_prompt:
            return None
        prompt = session.pending_voice_prompt
        session.pending_voice_prompt = None
        return prompt

    def system_hint(self, session_id: str) -> str | None:
        session = self._sessions.get(session_id)
        if not session or session.state in TERMINAL_STATES | {VoicePaymentState.IDLE}:
            return None
        return self._confirmation.system_hint(
            state=session.state.value,
            amount=session.amount,
            currency="KES",
        )

    async def ensure_session(
        self,
        *,
        session_id: str,
        organization_id: int,
        workflow_run_id: int,
        phone_e164: str,
        customer_name: str = "there",
        amount: float | None = None,
        language: str = "mixed",
    ) -> VoicePaymentSession:
        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing:
                return existing

            config = await self._voice_config(organization_id)
            resolved_amount = amount if amount is not None else config.default_amount
            session = VoicePaymentSession(
                session_id=session_id,
                organization_id=organization_id,
                workflow_run_id=workflow_run_id,
                phone_e164=normalize_telephony_address(phone_e164).canonical,
                customer_name=customer_name,
                amount=resolved_amount,
                language=language,
                account_reference=f"VR{workflow_run_id}"[:12],
            )
            self._sessions[session_id] = session
            return session

    async def on_user_utterance(
        self,
        session_id: str,
        text: str,
        *,
        intent: str | None = None,
        slots: dict[str, str] | None = None,
        interrupted: bool = False,
    ) -> VoicePaymentTurnResult:
        session = self._sessions.get(session_id)
        if session is None:
            return await self._maybe_auto_offer(
                session_id,
                text,
                intent=intent,
                slots=slots or {},
            )

        if interrupted and self._state_machine.is_awaiting_payment(session.state):
            return await self._handle_interrupt(session)

        if session.state == VoicePaymentState.INTERRUPTED:
            restored = await self._recovery.resume_after_interrupt(session)
            session.state = restored
            if self._confirmation.asks_payment_status(text):
                asyncio.create_task(self._verify_now(session.session_id))

        if session.state == VoicePaymentState.FAILED and self._confirmation.wants_retry(text):
            return await self._handle_retry_consent(session)

        if session.state == VoicePaymentState.AWAITING_CONSENT:
            if self._confirmation.is_consent(text):
                return await self._handle_consent(session)
            if self._confirmation.is_decline(text):
                return self._handle_decline(session)

        if self._confirmation.asks_payment_status(text) and session.transaction_id:
            asyncio.create_task(self._verify_now(session.session_id))
            return VoicePaymentTurnResult(
                handled=True,
                system_hint="Caller asked about payment status. Checking now.",
                state=session.state,
            )

        return VoicePaymentTurnResult(handled=False, state=session.state)

    async def offer_payment(
        self,
        session_id: str,
        *,
        amount: float | None = None,
    ) -> VoicePaymentTurnResult:
        session = self._sessions.get(session_id)
        if not session:
            return VoicePaymentTurnResult(handled=False)

        if amount is not None:
            session.amount = amount

        next_state = self._apply_event(session, VoicePaymentEvent.OFFER)
        if next_state is None:
            next_state = self._apply_event(session, VoicePaymentEvent.ASK_CONSENT)
        if next_state is None:
            return VoicePaymentTurnResult(handled=False, state=session.state)

        prompt = self._confirmation.offer_prompt(
            amount=session.amount,
            currency="KES",
            language=session.language,
        )
        session.pending_voice_prompt = prompt
        await self._persist_session(session)
        return VoicePaymentTurnResult(
            handled=True,
            speak_prompt=prompt,
            skip_llm_turn=True,
            state=session.state,
            event=VoicePaymentEvent.ASK_CONSENT,
        )

    async def on_payment_callback(
        self,
        *,
        transaction_id: int,
        organization_id: int,
        status: str,
        mpesa_receipt_number: str | None = None,
    ) -> None:
        session = await self._resolve_session_for_transaction(
            transaction_id,
            organization_id,
        )
        if not session:
            return
        if status == MpesaTransactionStatus.COMPLETED.value:
            session.mpesa_receipt_number = mpesa_receipt_number
            await self._complete_payment(session)
        elif status == MpesaTransactionStatus.CANCELLED.value:
            await self._fail_payment(session, cancelled=True)
        elif status in {
            MpesaTransactionStatus.FAILED.value,
            MpesaTransactionStatus.TIMEOUT.value,
        }:
            await self._fail_payment(session, cancelled=False)

    async def shutdown_session(self, session_id: str) -> None:
        watcher = self._watchers.pop(session_id, None)
        if watcher and not watcher.done():
            watcher.cancel()
        session = self._sessions.pop(session_id, None)
        if session:
            await self._persist_session(session)

    async def mark_receipt_sent(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        self._apply_event(session, VoicePaymentEvent.RECEIPT_SENT)
        await self._persist_session(session)

    async def _maybe_auto_offer(
        self,
        session_id: str,
        text: str,
        *,
        intent: str | None,
        slots: dict[str, str],
    ) -> VoicePaymentTurnResult:
        return VoicePaymentTurnResult(handled=False)

    async def register_from_memory(
        self,
        *,
        session_id: str,
        organization_id: int,
        workflow_run_id: int,
        phone_e164: str,
        customer_name: str,
        intent: str,
        slots: dict[str, str],
        language: str = "mixed",
    ) -> VoicePaymentTurnResult | None:
        config = await self._voice_config(organization_id)
        if not config.enabled or not config.auto_offer_on_payment_intent:
            return None
        if intent not in {CallIntent.REQUEST_PAYMENT.value, "request_payment"}:
            return None

        existing = self._sessions.get(session_id)
        if existing and existing.state not in {
            VoicePaymentState.IDLE,
            VoicePaymentState.OFFERED,
        }:
            return None

        amount = config.default_amount
        if slots.get("amount"):
            try:
                amount = float(slots["amount"])
            except ValueError:
                pass
        parsed = self._confirmation.parse_amount_from_text(
            " ".join(slots.values()) if slots else ""
        )
        if parsed:
            amount = parsed

        await self.ensure_session(
            session_id=session_id,
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            phone_e164=phone_e164,
            customer_name=customer_name,
            amount=amount,
            language=language,
        )
        return await self.offer_payment(session_id)

    async def _handle_consent(self, session: VoicePaymentSession) -> VoicePaymentTurnResult:
        next_state = self._apply_event(session, VoicePaymentEvent.CONSENT)
        if next_state is None:
            return VoicePaymentTurnResult(handled=False, state=session.state)

        session.state = VoicePaymentState.STK_PUSHING
        await self._persist_session(session)

        response = await self._stk.initiate_stk_push(
            STKPushRequest(
                phone_e164=session.phone_e164,
                amount=session.amount,
                account_reference=session.account_reference,
                transaction_desc="VoicePay",
                organization_id=session.organization_id,
                workflow_run_id=session.workflow_run_id,
                metadata={"voice_session_id": session.session_id},
            )
        )

        if not response.success:
            session.state = VoicePaymentState.FAILED
            prompt = self._confirmation.failed_prompt(
                language=session.language,
                can_retry=session.retry_count < (await self._voice_config(session.organization_id)).max_retries,
            )
            session.pending_voice_prompt = prompt
            await self._persist_session(session)
            return VoicePaymentTurnResult(
                handled=True,
                speak_prompt=prompt,
                skip_llm_turn=True,
                state=session.state,
                event=VoicePaymentEvent.STK_FAILED,
            )

        session.transaction_id = response.transaction_id
        self._apply_event(session, VoicePaymentEvent.STK_SENT)
        prompt = self._confirmation.stk_sent_prompt(language=session.language)
        session.pending_voice_prompt = prompt
        await self._log_event(session, MpesaEventType.STK_INITIATED.value, response.raw_response)
        await self._persist_session(session)
        self._start_watcher(session.session_id)

        return VoicePaymentTurnResult(
            handled=True,
            speak_prompt=prompt,
            skip_llm_turn=True,
            state=session.state,
            event=VoicePaymentEvent.STK_SENT,
        )

    def _handle_decline(self, session: VoicePaymentSession) -> VoicePaymentTurnResult:
        self._apply_event(session, VoicePaymentEvent.DECLINE)
        prompt = self._confirmation.cancelled_prompt(language=session.language)
        session.pending_voice_prompt = prompt
        return VoicePaymentTurnResult(
            handled=True,
            speak_prompt=prompt,
            skip_llm_turn=True,
            state=session.state,
            event=VoicePaymentEvent.DECLINE,
        )

    async def _handle_retry_consent(self, session: VoicePaymentSession) -> VoicePaymentTurnResult:
        config = await self._voice_config(session.organization_id)
        ok, error, tx_id = await self._recovery.retry_stk_push(session, config)
        if not ok:
            prompt = self._confirmation.failed_prompt(
                language=session.language,
                can_retry=session.retry_count < config.max_retries,
            )
            session.pending_voice_prompt = prompt
            return VoicePaymentTurnResult(
                handled=True,
                speak_prompt=prompt,
                skip_llm_turn=True,
                state=session.state,
            )

        session.transaction_id = tx_id
        self._apply_event(session, VoicePaymentEvent.STK_SENT)
        prompt = self._confirmation.stk_sent_prompt(language=session.language)
        session.pending_voice_prompt = prompt
        self._start_watcher(session.session_id)
        return VoicePaymentTurnResult(
            handled=True,
            speak_prompt=prompt,
            skip_llm_turn=True,
            state=session.state,
            event=VoicePaymentEvent.RETRY,
        )

    async def _handle_interrupt(self, session: VoicePaymentSession) -> VoicePaymentTurnResult:
        session.interrupted = True
        session.interrupted_from = session.state
        self._apply_event(session, VoicePaymentEvent.INTERRUPT)
        return VoicePaymentTurnResult(
            handled=True,
            system_hint=(
                "Caller interrupted during M-Pesa payment. "
                "Keep payment state; resume when they continue."
            ),
            state=session.state,
            event=VoicePaymentEvent.INTERRUPT,
        )

    async def _complete_payment(self, session: VoicePaymentSession) -> None:
        self._apply_event(session, VoicePaymentEvent.PAYMENT_SUCCESS)
        config = await self._voice_config(session.organization_id)
        prompt = self._confirmation.success_prompt(
            amount=session.amount,
            currency="KES",
            receipt=session.mpesa_receipt_number,
            language=session.language,
        )
        session.pending_voice_prompt = prompt
        self._apply_event(session, VoicePaymentEvent.VOICE_CONFIRMED)
        await self._persist_session(session)

        if config.send_whatsapp_receipt:
            from api.tasks.arq import enqueue_job

            await enqueue_job(
                FunctionNames.VOICE_MPESA_SEND_RECEIPT,
                session.session_id,
                session.organization_id,
            )
        else:
            self._apply_event(session, VoicePaymentEvent.RECEIPT_SENT)

        watcher = self._watchers.pop(session.session_id, None)
        if watcher and not watcher.done():
            watcher.cancel()

    async def _fail_payment(self, session: VoicePaymentSession, *, cancelled: bool) -> None:
        event = (
            VoicePaymentEvent.PAYMENT_CANCELLED if cancelled else VoicePaymentEvent.PAYMENT_FAILED
        )
        self._apply_event(session, event)
        config = await self._voice_config(session.organization_id)
        prompt = (
            self._confirmation.cancelled_prompt(language=session.language)
            if cancelled
            else self._confirmation.failed_prompt(
                language=session.language,
                can_retry=session.retry_count < config.max_retries,
            )
        )
        session.pending_voice_prompt = prompt
        await self._persist_session(session)

    def _start_watcher(self, session_id: str) -> None:
        existing = self._watchers.get(session_id)
        if existing and not existing.done():
            return
        self._watchers[session_id] = asyncio.create_task(
            self._watch_payment(session_id),
            name=f"voice-mpesa-watch-{session_id[:8]}",
        )

    async def _watch_payment(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session or not session.transaction_id:
            return

        config = await self._voice_config(session.organization_id)
        deadline = time.monotonic() + config.verification_timeout_s

        while time.monotonic() < deadline:
            session = self._sessions.get(session_id)
            if not session or session.state in TERMINAL_STATES | {
                VoicePaymentState.PAYMENT_CONFIRMED,
                VoicePaymentState.COMPLETED,
            }:
                return

            tx = await db_client.get_transaction(
                session.transaction_id,
                organization_id=session.organization_id,
            )
            if not tx:
                return

            if tx.status == MpesaTransactionStatus.COMPLETED.value:
                session.mpesa_receipt_number = tx.mpesa_receipt_number
                await self._complete_payment(session)
                return
            if tx.status == MpesaTransactionStatus.CANCELLED.value:
                await self._fail_payment(session, cancelled=True)
                return
            if tx.status in {
                MpesaTransactionStatus.FAILED.value,
                MpesaTransactionStatus.TIMEOUT.value,
            }:
                await self._fail_payment(session, cancelled=False)
                return

            if session.state == VoicePaymentState.AWAITING_PAYMENT:
                self._apply_event(session, VoicePaymentEvent.VERIFY_START)
                await self._stk.verify_transaction(
                    session.transaction_id,
                    organization_id=session.organization_id,
                )

            await asyncio.sleep(config.verification_poll_interval_s)

        await self._fail_payment(session, cancelled=False)

    async def _verify_now(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session or not session.transaction_id:
            return
        result = await self._stk.verify_transaction(
            session.transaction_id,
            organization_id=session.organization_id,
        )
        status = result.get("status")
        if status == MpesaTransactionStatus.COMPLETED.value:
            tx = await db_client.get_transaction(
                session.transaction_id,
                organization_id=session.organization_id,
            )
            if tx:
                session.mpesa_receipt_number = tx.mpesa_receipt_number
            await self._complete_payment(session)

    def _apply_event(
        self,
        session: VoicePaymentSession,
        event: VoicePaymentEvent,
    ) -> VoicePaymentState | None:
        next_state = self._state_machine.transition(session.state, event)
        if next_state is not None:
            session.state = next_state
        return next_state

    def _find_session_by_transaction(
        self,
        transaction_id: int,
        organization_id: int,
    ) -> VoicePaymentSession | None:
        for session in self._sessions.values():
            if (
                session.transaction_id == transaction_id
                and session.organization_id == organization_id
            ):
                return session
        return None

    async def _resolve_session_for_transaction(
        self,
        transaction_id: int,
        organization_id: int,
    ) -> VoicePaymentSession | None:
        session = self._find_session_by_transaction(transaction_id, organization_id)
        if session:
            return session

        tx = await db_client.get_transaction(transaction_id, organization_id=organization_id)
        if not tx:
            return None

        metadata = tx.metadata_json or {}
        voice_session_id = metadata.get("voice_session_id")
        if not voice_session_id:
            return None

        if voice_session_id in self._sessions:
            return self._sessions[voice_session_id]

        if tx.workflow_run_id:
            run = await db_client.get_workflow_run_by_id(tx.workflow_run_id)
            if run:
                ctx = (run.gathered_context or {}).get("voice_mpesa_payment") or {}
                if ctx.get("session_id") == voice_session_id:
                    session = VoicePaymentSession(
                        session_id=voice_session_id,
                        organization_id=organization_id,
                        workflow_run_id=tx.workflow_run_id,
                        phone_e164=ctx.get("phone_e164", tx.phone_e164),
                        customer_name=ctx.get("customer_name", "there"),
                        amount=float(ctx.get("amount", tx.amount)),
                        state=VoicePaymentState(ctx.get("state", VoicePaymentState.AWAITING_PAYMENT.value)),
                        transaction_id=transaction_id,
                        retry_count=int(ctx.get("retry_count", 0)),
                        language=ctx.get("language", "mixed"),
                        account_reference=ctx.get("account_reference", tx.account_reference),
                        mpesa_receipt_number=ctx.get("mpesa_receipt_number"),
                    )
                    self._sessions[voice_session_id] = session
                    return session

        session = VoicePaymentSession(
            session_id=voice_session_id,
            organization_id=organization_id,
            workflow_run_id=tx.workflow_run_id or 0,
            phone_e164=tx.phone_e164,
            customer_name="there",
            amount=tx.amount,
            state=VoicePaymentState.AWAITING_PAYMENT,
            transaction_id=transaction_id,
            account_reference=tx.account_reference,
        )
        self._sessions[voice_session_id] = session
        return session

    async def _voice_config(self, organization_id: int) -> VoiceMpesaConfig:
        cache_key = f"{ORG_CONFIG_KEY}:voice_payment"
        cache = mpesa_config_cache()
        cached = cache.get(organization_id, cache_key)
        if cached is not None:
            return cached
        row = await db_client.get_configuration(organization_id, ORG_CONFIG_KEY)
        raw = {}
        if row and row.value:
            raw = row.value.get("voice_payment") or {}
        config = VoiceMpesaConfig.from_dict(raw)
        cache.set(organization_id, cache_key, config)
        return config

    async def _persist_session(self, session: VoicePaymentSession) -> None:
        if not session.workflow_run_id:
            return
        await db_client.update_workflow_run(
            run_id=session.workflow_run_id,
            gathered_context={"voice_mpesa_payment": session.to_dict()},
        )

    async def _log_event(
        self,
        session: VoicePaymentSession,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if not session.transaction_id:
            return
        await db_client.append_event(
            transaction_id=session.transaction_id,
            event_type=event_type,
            payload={"voice_session_id": session.session_id, **payload},
        )


_engine: VoiceMpesaWorkflowEngine | None = None


def get_voice_mpesa_engine() -> VoiceMpesaWorkflowEngine:
    global _engine
    if _engine is None:
        _engine = VoiceMpesaWorkflowEngine()
    return _engine
