from __future__ import annotations

from api.services.kenyan_intent.types import (
    BusinessIntent,
    ClassificationResult,
    RouteAction,
    RouteDecision,
)


class IntentRoutingEngine:
    """Route detected intents to downstream voice / business actions."""

    _PRIORITY: dict[BusinessIntent, int] = {
        BusinessIntent.ESCALATION: 100,
        BusinessIntent.PAYMENT: 90,
        BusinessIntent.CANCELLATION: 85,
        BusinessIntent.BOOKING: 80,
        BusinessIntent.APPOINTMENT: 80,
        BusinessIntent.COMPLAINT: 75,
        BusinessIntent.CALLBACK: 70,
        BusinessIntent.DELIVERY: 65,
        BusinessIntent.ORDER: 65,
        BusinessIntent.BALANCE_INQUIRY: 62,
        BusinessIntent.ACCOUNT_INQUIRY: 62,
        BusinessIntent.LOCATION_INQUIRY: 61,
        BusinessIntent.SUPPORT: 60,
        BusinessIntent.CONFIRMATION: 40,
        BusinessIntent.UNKNOWN: 0,
        BusinessIntent.INTERRUPTION: 0,
    }

    _ACTION_MAP: dict[BusinessIntent, RouteAction] = {
        BusinessIntent.PAYMENT: RouteAction.TRIGGER_MPESA_PAYMENT,
        BusinessIntent.BOOKING: RouteAction.TRIGGER_BOOKING,
        BusinessIntent.APPOINTMENT: RouteAction.TRIGGER_BOOKING,
        BusinessIntent.ESCALATION: RouteAction.TRIGGER_ESCALATION,
        BusinessIntent.SUPPORT: RouteAction.ROUTE_SUPPORT,
        BusinessIntent.COMPLAINT: RouteAction.ROUTE_SUPPORT,
        BusinessIntent.CALLBACK: RouteAction.SCHEDULE_CALLBACK,
        BusinessIntent.UNKNOWN: RouteAction.CONTINUE,
        BusinessIntent.INTERRUPTION: RouteAction.CONTINUE,
    }

    def route(
        self,
        result: ClassificationResult,
        *,
        confidence_threshold: float = 0.6,
        interrupted: bool = False,
    ) -> RouteDecision:
        if interrupted and result.intent == BusinessIntent.UNKNOWN:
            return RouteDecision(
                action=RouteAction.CONTINUE,
                intent=BusinessIntent.INTERRUPTION,
                confidence=result.confidence,
                priority=0,
                reason="Interrupted — hold routing until final transcript",
                metadata={"interrupted": True},
            )

        if result.confidence < confidence_threshold:
            return RouteDecision(
                action=RouteAction.CONTINUE,
                intent=result.intent,
                confidence=result.confidence,
                priority=self._PRIORITY.get(result.intent, 0),
                reason="Confidence below routing threshold",
                slots=result.slots,
            )

        action = self._ACTION_MAP.get(result.intent, RouteAction.CONTINUE)
        if action == RouteAction.CONTINUE:
            return RouteDecision(
                action=action,
                intent=result.intent,
                confidence=result.confidence,
                priority=self._PRIORITY.get(result.intent, 0),
                reason="No actionable business intent",
                slots=result.slots,
            )

        return RouteDecision(
            action=action,
            intent=result.intent,
            confidence=result.confidence,
            priority=self._PRIORITY.get(result.intent, 0),
            reason=self._reason_for(result.intent),
            slots=result.slots,
            metadata={
                "language": result.language,
                "matched_phrases": result.matched_phrases,
                "latency_ms": result.latency_ms,
            },
        )

    @staticmethod
    def _reason_for(intent: BusinessIntent) -> str:
        return {
            BusinessIntent.PAYMENT: "Caller wants to make a payment",
            BusinessIntent.BOOKING: "Caller wants to book or confirm an appointment",
            BusinessIntent.ESCALATION: "Caller requested a human agent",
            BusinessIntent.SUPPORT: "Caller needs technical or account support",
            BusinessIntent.CALLBACK: "Caller requested a callback",
        }.get(intent, "Continue conversation")
