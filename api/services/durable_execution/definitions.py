"""Orchestration definition registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from api.services.durable_execution.types import OrchestrationContext, StepOutcome

StepHandler = Callable[[OrchestrationContext], Awaitable[StepOutcome]]
CompensationHandler = Callable[[OrchestrationContext, dict], Awaitable[StepOutcome]]


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    handler: StepHandler
    compensation_handler: CompensationHandler | None = None
    max_retries: int = 3
    retry_delay_s: float = 30.0


@dataclass(frozen=True)
class OrchestrationDefinition:
    name: str
    entry_step: str
    steps: dict[str, StepDefinition] = field(default_factory=dict)
    terminal_steps: frozenset[str] = frozenset()

    def step(self, step_id: str) -> StepDefinition | None:
        return self.steps.get(step_id)


class DefinitionRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, OrchestrationDefinition] = {}

    def register(self, definition: OrchestrationDefinition) -> None:
        self._definitions[definition.name] = definition

    def get(self, name: str) -> OrchestrationDefinition:
        definition = self._definitions.get(name)
        if definition is None:
            raise KeyError(f"Unknown orchestration definition: {name}")
        return definition

    def list_names(self) -> list[str]:
        return sorted(self._definitions.keys())


_registry: DefinitionRegistry | None = None


def get_definition_registry() -> DefinitionRegistry:
    global _registry
    if _registry is None:
        _registry = DefinitionRegistry()
        from api.services.durable_execution.builtin_definitions import register_builtin_definitions

        register_builtin_definitions(_registry)
    return _registry
