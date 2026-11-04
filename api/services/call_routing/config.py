from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.constants import CALL_ROUTING_ENABLED, CALL_ROUTING_QUEUE_TTL_S
from api.enums import OrganizationConfigurationKey
from api.services.call_routing.types import RoutingDestination
from api.services.kenyan_intent.types import RouteAction

ORG_CONFIG_KEY = OrganizationConfigurationKey.CALL_ROUTING_CONFIGURATION.value


@dataclass(frozen=True)
class QueueConfig:
    name: str
    max_wait_s: int = 300
    max_depth: int = 50

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> QueueConfig:
        return cls(
            name=raw.get("name", "default"),
            max_wait_s=int(raw.get("max_wait_s", 300)),
            max_depth=int(raw.get("max_depth", 50)),
        )


@dataclass(frozen=True)
class EscalationRoutingConfig:
    transfer_destination: str = ""
    notify_numbers: tuple[str, ...] = ()
    webhook_url: str | None = None
    auto_transfer: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> EscalationRoutingConfig:
        raw = raw or {}
        return cls(
            transfer_destination=str(raw.get("transfer_destination", "")),
            notify_numbers=tuple(raw.get("notify_numbers") or ()),
            webhook_url=raw.get("webhook_url"),
            auto_transfer=bool(raw.get("auto_transfer", True)),
        )


@dataclass(frozen=True)
class FallbackConfig:
    strategy: str = "continue_ai"
    offer_callback: bool = True
    max_queue_retries: int = 2
    low_confidence_threshold: float = 0.45

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> FallbackConfig:
        raw = raw or {}
        return cls(
            strategy=str(raw.get("strategy", "continue_ai")),
            offer_callback=bool(raw.get("offer_callback", True)),
            max_queue_retries=int(raw.get("max_queue_retries", 2)),
            low_confidence_threshold=float(raw.get("low_confidence_threshold", 0.45)),
        )


@dataclass(frozen=True)
class CallRoutingOrgConfig:
    enabled: bool
    default_language: str
    queues: dict[str, QueueConfig]
    escalation: EscalationRoutingConfig
    fallback: FallbackConfig
    language_queues: dict[str, dict[str, str]]

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> CallRoutingOrgConfig:
        if not raw:
            return cls(
                enabled=CALL_ROUTING_ENABLED,
                default_language="mixed",
                queues=_default_queues(),
                escalation=EscalationRoutingConfig(),
                fallback=FallbackConfig(),
                language_queues=_default_language_queues(),
            )

        queues_raw = raw.get("queues") or {}
        queues = {
            key: QueueConfig.from_dict({"name": key, **(val if isinstance(val, dict) else {})})
            for key, val in (queues_raw or _default_queues()).items()
        }
        if not queues:
            queues = _default_queues()

        return cls(
            enabled=bool(raw.get("enabled", CALL_ROUTING_ENABLED)),
            default_language=str(raw.get("default_language", "mixed")),
            queues=queues,
            escalation=EscalationRoutingConfig.from_dict(raw.get("escalation")),
            fallback=FallbackConfig.from_dict(raw.get("fallback")),
            language_queues=dict(raw.get("language_queues") or _default_language_queues()),
        )


@dataclass(frozen=True)
class CallRoutingRuntimeConfig:
    enabled: bool = CALL_ROUTING_ENABLED
    queue_ttl_s: int = CALL_ROUTING_QUEUE_TTL_S
    route_confidence_threshold: float = 0.6


DEFAULT_CALL_ROUTING_CONFIG = CallRoutingRuntimeConfig()


def _default_queues() -> dict[str, QueueConfig]:
    return {
        "human": QueueConfig(name="human", max_wait_s=300),
        "support": QueueConfig(name="support", max_wait_s=240),
        "booking": QueueConfig(name="booking", max_wait_s=180),
        "callback": QueueConfig(name="callback", max_wait_s=600),
    }


def _default_language_queues() -> dict[str, dict[str, str]]:
    return {
        "en": {
            "human": "human_en",
            "support": "support_en",
            "booking": "booking_en",
            "callback": "callback_en",
        },
        "sw": {
            "human": "human_sw",
            "support": "support_sw",
            "booking": "booking_sw",
            "callback": "callback_sw",
        },
        "mixed": {
            "human": "human",
            "support": "support",
            "booking": "booking",
            "callback": "callback",
        },
    }


_ACTION_DESTINATION: dict[RouteAction, tuple[RoutingDestination, str]] = {
    RouteAction.TRIGGER_ESCALATION: (RoutingDestination.HUMAN_QUEUE, "human"),
    RouteAction.ROUTE_SUPPORT: (RoutingDestination.SUPPORT_QUEUE, "support"),
    RouteAction.TRIGGER_BOOKING: (RoutingDestination.BOOKING_QUEUE, "booking"),
    RouteAction.SCHEDULE_CALLBACK: (RoutingDestination.CALLBACK_QUEUE, "callback"),
    RouteAction.TRIGGER_MPESA_PAYMENT: (RoutingDestination.PAYMENT_FLOW, ""),
    RouteAction.CONTINUE: (RoutingDestination.AI_AGENT, ""),
    RouteAction.NONE: (RoutingDestination.AI_AGENT, ""),
}


def destination_for_action(action: RouteAction) -> tuple[RoutingDestination, str]:
    return _ACTION_DESTINATION[action]
