from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoicePaymentState(str, Enum):
    IDLE = "idle"
    OFFERED = "offered"
    AWAITING_CONSENT = "awaiting_consent"
    CONSENTED = "consented"
    STK_PUSHING = "stk_pushing"
    AWAITING_PAYMENT = "awaiting_payment"
    VERIFYING = "verifying"
    PAYMENT_CONFIRMED = "payment_confirmed"
    RECEIPT_PENDING = "receipt_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    DECLINED = "declined"
    INTERRUPTED = "interrupted"


class VoicePaymentEvent(str, Enum):
    OFFER = "offer"
    ASK_CONSENT = "ask_consent"
    CONSENT = "consent"
    DECLINE = "decline"
    INTERRUPT = "interrupt"
    RESUME = "resume"
    STK_SENT = "stk_sent"
    STK_FAILED = "stk_failed"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_CANCELLED = "payment_cancelled"
    VERIFY_START = "verify_start"
    VOICE_CONFIRMED = "voice_confirmed"
    RECEIPT_SENT = "receipt_sent"
    RETRY = "retry"


TERMINAL_STATES = frozenset(
    {
        VoicePaymentState.COMPLETED,
        VoicePaymentState.DECLINED,
    }
)


@dataclass
class VoicePaymentSession:
    session_id: str
    organization_id: int
    workflow_run_id: int
    phone_e164: str
    customer_name: str
    amount: float
    state: VoicePaymentState = VoicePaymentState.IDLE
    transaction_id: int | None = None
    retry_count: int = 0
    language: str = "mixed"
    interrupted: bool = False
    interrupted_from: VoicePaymentState | None = None
    pending_voice_prompt: str | None = None
    account_reference: str = ""
    mpesa_receipt_number: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "phone_e164": self.phone_e164,
            "customer_name": self.customer_name,
            "amount": self.amount,
            "state": self.state.value,
            "transaction_id": self.transaction_id,
            "retry_count": self.retry_count,
            "language": self.language,
            "interrupted": self.interrupted,
            "pending_voice_prompt": self.pending_voice_prompt,
            "account_reference": self.account_reference,
            "mpesa_receipt_number": self.mpesa_receipt_number,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class VoicePaymentTurnResult:
    handled: bool
    system_hint: str | None = None
    skip_llm_turn: bool = False
    speak_prompt: str | None = None
    state: VoicePaymentState | None = None
    event: VoicePaymentEvent | None = None
