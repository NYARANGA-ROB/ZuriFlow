from __future__ import annotations

from typing import Any

from api.services.whatsapp.post_call.config import PostCallWorkflowConfig
from api.services.whatsapp.post_call.types import PostCallSummary


class PostCallEscalationEvaluator:
    """Decide whether a completed call should be escalated to a human."""

    def should_escalate(
        self,
        *,
        summary: PostCallSummary,
        gathered_context: dict[str, Any],
        config: PostCallWorkflowConfig,
    ) -> tuple[bool, str]:
        if gathered_context.get("escalate_to_human") is True:
            return True, "Explicit escalation flag in call context"

        disposition = str(
            gathered_context.get("mapped_call_disposition")
            or gathered_context.get("call_disposition")
            or ""
        ).lower()
        if disposition and any(token in disposition for token in config.escalate_on_dispositions):
            return True, f"Call disposition: {disposition}"

        if summary.intent in config.escalate_on_intents:
            return True, f"Intent requires human follow-up: {summary.intent}"

        if config.escalate_on_low_confidence and summary.intent_confidence < config.confidence_threshold:
            if summary.intent not in ("unknown", "greeting", "farewell", "gratitude"):
                return True, (
                    f"Low intent confidence ({summary.intent_confidence:.2f} "
                    f"< {config.confidence_threshold})"
                )

        if gathered_context.get("interrupted") and summary.intent == "request_support":
            return True, "Interrupted support call"

        tags = gathered_context.get("call_tags") or []
        if isinstance(tags, list) and any(
            str(tag).lower() in ("escalate", "human_handoff", "failed_resolution")
            for tag in tags
        ):
            return True, "Escalation tag on call"

        return False, ""
