from __future__ import annotations

from api.services.voice_mpesa.types import VoicePaymentEvent, VoicePaymentState

_TRANSITIONS: dict[tuple[VoicePaymentState, VoicePaymentEvent], VoicePaymentState] = {
    (VoicePaymentState.IDLE, VoicePaymentEvent.OFFER): VoicePaymentState.OFFERED,
    (VoicePaymentState.IDLE, VoicePaymentEvent.ASK_CONSENT): VoicePaymentState.AWAITING_CONSENT,
    (VoicePaymentState.OFFERED, VoicePaymentEvent.ASK_CONSENT): VoicePaymentState.AWAITING_CONSENT,
    (VoicePaymentState.AWAITING_CONSENT, VoicePaymentEvent.CONSENT): VoicePaymentState.CONSENTED,
    (VoicePaymentState.AWAITING_CONSENT, VoicePaymentEvent.DECLINE): VoicePaymentState.DECLINED,
    (VoicePaymentState.AWAITING_CONSENT, VoicePaymentEvent.INTERRUPT): VoicePaymentState.INTERRUPTED,
    (VoicePaymentState.INTERRUPTED, VoicePaymentEvent.RESUME): VoicePaymentState.AWAITING_CONSENT,
    (VoicePaymentState.CONSENTED, VoicePaymentEvent.STK_SENT): VoicePaymentState.AWAITING_PAYMENT,
    (VoicePaymentState.STK_PUSHING, VoicePaymentEvent.STK_SENT): VoicePaymentState.AWAITING_PAYMENT,
    (VoicePaymentState.STK_PUSHING, VoicePaymentEvent.STK_FAILED): VoicePaymentState.FAILED,
    (VoicePaymentState.AWAITING_PAYMENT, VoicePaymentEvent.VERIFY_START): VoicePaymentState.VERIFYING,
    (VoicePaymentState.AWAITING_PAYMENT, VoicePaymentEvent.PAYMENT_SUCCESS): VoicePaymentState.PAYMENT_CONFIRMED,
    (VoicePaymentState.AWAITING_PAYMENT, VoicePaymentEvent.PAYMENT_FAILED): VoicePaymentState.FAILED,
    (VoicePaymentState.AWAITING_PAYMENT, VoicePaymentEvent.PAYMENT_CANCELLED): VoicePaymentState.FAILED,
    (VoicePaymentState.AWAITING_PAYMENT, VoicePaymentEvent.INTERRUPT): VoicePaymentState.INTERRUPTED,
    (VoicePaymentState.VERIFYING, VoicePaymentEvent.PAYMENT_SUCCESS): VoicePaymentState.PAYMENT_CONFIRMED,
    (VoicePaymentState.VERIFYING, VoicePaymentEvent.PAYMENT_FAILED): VoicePaymentState.FAILED,
    (VoicePaymentState.VERIFYING, VoicePaymentEvent.PAYMENT_CANCELLED): VoicePaymentState.FAILED,
    (VoicePaymentState.PAYMENT_CONFIRMED, VoicePaymentEvent.VOICE_CONFIRMED): VoicePaymentState.RECEIPT_PENDING,
    (VoicePaymentState.RECEIPT_PENDING, VoicePaymentEvent.RECEIPT_SENT): VoicePaymentState.COMPLETED,
    (VoicePaymentState.FAILED, VoicePaymentEvent.RETRY): VoicePaymentState.CONSENTED,
    (VoicePaymentState.FAILED, VoicePaymentEvent.ASK_CONSENT): VoicePaymentState.AWAITING_CONSENT,
}


class VoicePaymentStateMachine:
    """Explicit payment state transitions for voice calls."""

    def transition(
        self,
        current: VoicePaymentState,
        event: VoicePaymentEvent,
    ) -> VoicePaymentState | None:
        if current in {VoicePaymentState.COMPLETED, VoicePaymentState.DECLINED}:
            return None
        if event == VoicePaymentEvent.OFFER and current == VoicePaymentState.AWAITING_CONSENT:
            return current
        if event == VoicePaymentEvent.CONSENT and current == VoicePaymentState.FAILED:
            return VoicePaymentState.CONSENTED
        next_state = _TRANSITIONS.get((current, event))
        if next_state is None and event == VoicePaymentEvent.STK_SENT:
            if current == VoicePaymentState.CONSENTED:
                return VoicePaymentState.AWAITING_PAYMENT
        return next_state

    def can_initiate_stk(self, state: VoicePaymentState) -> bool:
        return state in {
            VoicePaymentState.CONSENTED,
            VoicePaymentState.FAILED,
        }

    def is_awaiting_payment(self, state: VoicePaymentState) -> bool:
        return state in {
            VoicePaymentState.AWAITING_PAYMENT,
            VoicePaymentState.VERIFYING,
        }
