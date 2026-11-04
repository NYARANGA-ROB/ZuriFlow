"""Types for durable orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrchestrationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    CANCELLED = "cancelled"


class ScheduledTaskStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledTaskType(str, Enum):
    EXECUTE_STEP = "execute_step"
    RETRY_STEP = "retry_step"
    WAKE_ORCHESTRATION = "wake_orchestration"
    COMPENSATE = "compensate"


class OrchestrationEventType(str, Enum):
    STARTED = "started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    SIGNAL_RECEIVED = "signal_received"
    WAITING = "waiting"
    SCHEDULED = "scheduled"
    COMPENSATION_STARTED = "compensation_started"
    COMPENSATION_COMPLETED = "compensation_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepOutcomeType(str, Enum):
    COMPLETE = "complete"
    ADVANCE = "advance"
    WAIT = "wait"
    SCHEDULE = "schedule"
    FAIL = "fail"


@dataclass
class StepOutcome:
    outcome_type: StepOutcomeType
    next_step: str | None = None
    wake_at: datetime | None = None
    state_updates: dict[str, Any] | None = None
    error: str | None = None
    schedule_delay_s: float | None = None

    @classmethod
    def complete(cls, *, state_updates: dict[str, Any] | None = None) -> StepOutcome:
        return cls(StepOutcomeType.COMPLETE, state_updates=state_updates)

    @classmethod
    def advance(
        cls,
        next_step: str,
        *,
        state_updates: dict[str, Any] | None = None,
    ) -> StepOutcome:
        return cls(
            StepOutcomeType.ADVANCE,
            next_step=next_step,
            state_updates=state_updates,
        )

    @classmethod
    def wait(
        cls,
        *,
        state_updates: dict[str, Any] | None = None,
        wake_at: datetime | None = None,
    ) -> StepOutcome:
        return cls(StepOutcomeType.WAIT, state_updates=state_updates, wake_at=wake_at)

    @classmethod
    def schedule(
        cls,
        *,
        delay_s: float,
        state_updates: dict[str, Any] | None = None,
    ) -> StepOutcome:
        return cls(
            StepOutcomeType.SCHEDULE,
            schedule_delay_s=delay_s,
            state_updates=state_updates,
        )

    @classmethod
    def fail(cls, error: str) -> StepOutcome:
        return cls(StepOutcomeType.FAIL, error=error)


@dataclass
class SagaRecord:
    step_id: str
    compensation_step_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "compensation_step_id": self.compensation_step_id,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SagaRecord:
        return cls(
            step_id=str(raw["step_id"]),
            compensation_step_id=raw.get("compensation_step_id"),
            payload=dict(raw.get("payload") or {}),
        )


@dataclass
class OrchestrationContext:
    orchestration_id: int
    organization_id: int
    definition_name: str
    orchestration_key: str
    workflow_run_id: int | None
    current_step: str
    status: OrchestrationStatus
    state: dict[str, Any]
    saga_stack: list[SagaRecord]
    attempt: int = 1

    @property
    def variables(self) -> dict[str, Any]:
        return self.state


@dataclass
class OrchestrationResult:
    orchestration_id: int
    organization_id: int
    definition_name: str
    orchestration_key: str
    status: OrchestrationStatus
    current_step: str
    state: dict[str, Any]
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "orchestration_id": self.orchestration_id,
            "organization_id": self.organization_id,
            "definition_name": self.definition_name,
            "orchestration_key": self.orchestration_key,
            "status": self.status.value,
            "current_step": self.current_step,
            "state": dict(self.state),
            "error_message": self.error_message,
        }
