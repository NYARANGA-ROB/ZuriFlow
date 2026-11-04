from __future__ import annotations

import re
from typing import Any

from api.services.whatsapp.types import WhatsAppTemplateName

_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


PRESET_TEMPLATES: dict[str, str] = {
    WhatsAppTemplateName.CALL_SUMMARY.value: (
        "Hi {{customer_name}}, thanks for speaking with us.\n\n"
        "Call summary:\n{{summary}}\n\n"
        "Intent: {{intent}}\n"
        "Next steps: {{next_steps}}"
    ),
    WhatsAppTemplateName.PAYMENT_LINK.value: (
        "Hi {{customer_name}}, here is your payment link for {{amount}}:\n"
        "{{payment_url}}\n\n"
        "Reference: {{reference}}"
    ),
    WhatsAppTemplateName.APPOINTMENT_CONFIRMATION.value: (
        "Hi {{customer_name}}, your appointment is confirmed.\n\n"
        "Date: {{appointment_date}}\n"
        "Time: {{appointment_time}}\n"
        "Location: {{location}}\n\n"
        "Reply if you need to reschedule."
    ),
    WhatsAppTemplateName.ESCALATION_HANDOFF.value: (
        "A customer needs human assistance.\n\n"
        "Phone: {{customer_phone}}\n"
        "Reason: {{reason}}\n"
        "Context: {{context}}"
    ),
    WhatsAppTemplateName.GENERIC_TEXT.value: "{{body}}",
}


class WhatsAppTemplateEngine:
    """Render WhatsApp message bodies from named presets or custom templates."""

    def __init__(self, presets: dict[str, str] | None = None) -> None:
        self._presets = dict(PRESET_TEMPLATES)
        if presets:
            self._presets.update(presets)

    def render(self, template_name: str, variables: dict[str, Any]) -> str:
        template = self._presets.get(template_name)
        if template is None:
            raise KeyError(f"Unknown WhatsApp template: {template_name}")

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            value = variables.get(key)
            return "" if value is None else str(value)

        return _VAR_PATTERN.sub(replace, template).strip()

    def list_templates(self) -> list[str]:
        return sorted(self._presets.keys())
