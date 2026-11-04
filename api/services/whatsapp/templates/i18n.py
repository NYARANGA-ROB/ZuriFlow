from __future__ import annotations

from api.services.whatsapp.types import WhatsAppTemplateName

LOCALIZED_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
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
        "escalation_customer_ack": (
            "Thanks for your patience. A human agent will follow up with you "
            "on WhatsApp shortly."
        ),
    },
    "sw": {
        WhatsAppTemplateName.CALL_SUMMARY.value: (
            "Habari {{customer_name}}, asante kwa kuzungumza nasi.\n\n"
            "Muhtasari wa simu:\n{{summary}}\n\n"
            "Lengo: {{intent}}\n"
            "Hatua zinazofuata: {{next_steps}}"
        ),
        WhatsAppTemplateName.PAYMENT_LINK.value: (
            "Habari {{customer_name}}, hii ndiyo kiungo chako cha malipo kwa {{amount}}:\n"
            "{{payment_url}}\n\n"
            "Rejea: {{reference}}"
        ),
        WhatsAppTemplateName.APPOINTMENT_CONFIRMATION.value: (
            "Habari {{customer_name}}, miadi yako imethibitishwa.\n\n"
            "Tarehe: {{appointment_date}}\n"
            "Muda: {{appointment_time}}\n"
            "Mahali: {{location}}\n\n"
            "Jibu ikiwa unahitaji kubadilisha ratiba."
        ),
        WhatsAppTemplateName.ESCALATION_HANDOFF.value: (
            "Mteja anahitaji msaada wa binadamu.\n\n"
            "Simu: {{customer_phone}}\n"
            "Sababu: {{reason}}\n"
            "Muktadha: {{context}}"
        ),
        "escalation_customer_ack": (
            "Asante kwa uvumilivu wako. Wakala atawasiliana nawe kupitia WhatsApp hivi karibuni."
        ),
    },
    "mixed": {
        WhatsAppTemplateName.CALL_SUMMARY.value: (
            "Hi {{customer_name}}, thanks / asante kwa kuzungumza nasi.\n\n"
            "Call summary / Muhtasari:\n{{summary}}\n\n"
            "Intent / Lengo: {{intent}}\n"
            "Next steps / Hatua: {{next_steps}}"
        ),
        WhatsAppTemplateName.PAYMENT_LINK.value: (
            "Hi {{customer_name}}, payment link / kiungo cha malipo for {{amount}}:\n"
            "{{payment_url}}\n\n"
            "Reference / Rejea: {{reference}}"
        ),
        WhatsAppTemplateName.APPOINTMENT_CONFIRMATION.value: (
            "Hi {{customer_name}}, appointment / miadi confirmed.\n\n"
            "Date / Tarehe: {{appointment_date}}\n"
            "Time / Muda: {{appointment_time}}\n"
            "Location / Mahali: {{location}}"
        ),
        WhatsAppTemplateName.ESCALATION_HANDOFF.value: (
            "Customer needs human help / Mteja anahitaji msaada.\n\n"
            "Phone: {{customer_phone}}\n"
            "Reason: {{reason}}\n"
            "Context: {{context}}"
        ),
        "escalation_customer_ack": (
            "Thanks for waiting / Asante. A human agent will follow up on WhatsApp shortly."
        ),
    },
}

SWAHILI_MARKERS = (
    "habari",
    "asante",
    "sawa",
    "ndio",
    "nataka",
    "salio",
    "lipa",
    "saidia",
    "miadi",
    "tarehe",
)


def detect_language(text: str, default: str = "en") -> str:
    if not text:
        return default
    lowered = text.lower()
    sw_hits = sum(1 for marker in SWAHILI_MARKERS if marker in lowered)
    if sw_hits >= 2:
        return "sw"
    if default in LOCALIZED_TEMPLATES:
        return default
    return "en"
