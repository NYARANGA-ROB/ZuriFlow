"""Provider-independent telephony domain types.

Workflows and campaigns speak these types. Adapter packages under
``providers/`` are the only place that may mention Africa's Talking, Twilio,
ARI, or WebRTC protocol details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class CallCommand(str, Enum):
    """Workflow-facing commands. The engine never names a carrier."""

    START_CALL = "START_CALL"


class CallEventType(str, Enum):
    CALL_STARTED = "CALL_STARTED"
    CALL_RINGING = "CALL_RINGING"
    CALL_ANSWERED = "CALL_ANSWERED"
    CALL_ENDED = "CALL_ENDED"
    CALL_FAILED = "CALL_FAILED"
    DTMF_RECEIVED = "DTMF_RECEIVED"
    MEDIA_STARTED = "MEDIA_STARTED"


class CallTransport(str, Enum):
    PSTN = "pstn"
    WEBRTC = "webrtc"
    SIP = "sip"


class CallPurpose(str, Enum):
    TRANSACTIONAL = "transactional"
    MARKETING = "marketing"
    TEST = "test"


@dataclass(frozen=True)
class PhoneNumber:
    """Dialable address after Kenyan/E.164 normalization."""

    e164: str
    original: str
    country: str | None = None
    operator: str | None = None


@dataclass
class VoiceCall:
    """A live or queued call independent of the executing provider."""

    workflow_run_id: int
    organization_id: int
    to: PhoneNumber
    command: CallCommand = CallCommand.START_CALL
    from_number: str | None = None
    transport: CallTransport = CallTransport.PSTN
    provider_name: str | None = None
    provider_call_id: str | None = None
    telephony_configuration_id: int | None = None
    campaign_id: int | None = None
    purpose: CallPurpose = CallPurpose.TRANSACTIONAL


@dataclass
class CallSession:
    """Media session bound to a workflow run."""

    workflow_run_id: int
    organization_id: int
    transport: CallTransport
    provider_name: str
    media_started: bool = False
    websocket_connected: bool = False


@dataclass
class CallEvent:
    type: CallEventType
    workflow_run_id: int | None = None
    provider_call_id: str | None = None
    occurred_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    digit: str | None = None
    detail: str | None = None
    raw_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "workflow_run_id": self.workflow_run_id,
            "provider_call_id": self.provider_call_id,
            "occurred_at": self.occurred_at,
            "digit": self.digit,
            "detail": self.detail,
            "raw_status": self.raw_status,
            "metadata": dict(self.metadata),
        }


@dataclass
class CallRecording:
    """Pointer to stored call audio. No raw media bytes."""

    workflow_run_id: int
    organization_id: int
    storage_url: str | None
    duration_seconds: float | None = None
    storage_backend: str | None = None
