from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MpesaEnvironment(str, Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class MpesaTransactionStatus(str, Enum):
    PENDING = "pending"
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class MpesaEventType(str, Enum):
    CREATED = "created"
    STK_INITIATED = "stk_initiated"
    STK_INIT_FAILED = "stk_init_failed"
    CALLBACK_RECEIVED = "callback_received"
    CALLBACK_PROCESSED = "callback_processed"
    QUERY_REQUESTED = "query_requested"
    QUERY_RESULT = "query_result"
    RETRY_SCHEDULED = "retry_scheduled"
    VERIFIED = "verified"


@dataclass(frozen=True)
class DarajaToken:
    access_token: str
    expires_at: float


@dataclass(frozen=True)
class STKPushRequest:
    phone_e164: str
    amount: float
    account_reference: str
    transaction_desc: str
    organization_id: int
    workflow_run_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class STKPushResponse:
    success: bool
    transaction_id: int | None = None
    merchant_request_id: str | None = None
    checkout_request_id: str | None = None
    customer_message: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class STKCallbackResult:
    checkout_request_id: str
    merchant_request_id: str | None
    result_code: int
    result_desc: str
    mpesa_receipt_number: str | None = None
    amount: float | None = None
    phone_number: str | None = None
    transaction_date: str | None = None
    metadata_items: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.result_code == 0


@dataclass(frozen=True)
class STKQueryResult:
    success: bool
    result_code: int | None = None
    result_desc: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
