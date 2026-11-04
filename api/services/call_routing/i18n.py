from __future__ import annotations

from api.services.call_routing.types import RoutingDestination

_QUEUED_EN: dict[RoutingDestination, str] = {
    RoutingDestination.HUMAN_QUEUE: (
        "Please hold while I connect you to a human agent."
    ),
    RoutingDestination.SUPPORT_QUEUE: (
        "I'll route you to our support team. One moment please."
    ),
    RoutingDestination.BOOKING_QUEUE: (
        "Let me connect you with someone who can help with your booking."
    ),
    RoutingDestination.CALLBACK_QUEUE: (
        "I'll schedule a callback for you. Please stay on the line."
    ),
    RoutingDestination.FALLBACK_AI: (
        "Our agents are busy. I'll continue helping you for now."
    ),
}

_QUEUED_SW: dict[RoutingDestination, str] = {
    RoutingDestination.HUMAN_QUEUE: (
        "Tafadhali subiri nikukuunganishe na mtu."
    ),
    RoutingDestination.SUPPORT_QUEUE: (
        "Nitakuunganisha na timu ya msaada. Subiri kidogo."
    ),
    RoutingDestination.BOOKING_QUEUE: (
        "Nitakuunganisha na mtu wa miadi. Subiri kidogo."
    ),
    RoutingDestination.CALLBACK_QUEUE: (
        "Nitapanga kupiga simu tena. Tafadhali subiri."
    ),
    RoutingDestination.FALLBACK_AI: (
        "Wakala wetu wako busy. Nitaendelea kukusaidia."
    ),
}

_ESCALATION_ACK_EN = (
    "A human agent will assist you shortly. Thank you for your patience."
)
_ESCALATION_ACK_SW = (
    "Mtu atakusaidia hivi karibuni. Asante kwa uvumilivu wako."
)
_CALLBACK_OFFER_EN = (
    "Would you like us to call you back when an agent is available?"
)
_CALLBACK_OFFER_SW = (
    "Ungependa tupige simu tena mtu akipatikana?"
)


def voice_prompt_for_destination(
    destination: RoutingDestination,
    *,
    language: str = "mixed",
    queue_name: str = "",
) -> str:
    if language == "sw":
        base = _QUEUED_SW.get(destination, "")
    elif language == "en":
        base = _QUEUED_EN.get(destination, "")
    else:
        en = _QUEUED_EN.get(destination, "")
        sw = _QUEUED_SW.get(destination, "")
        base = f"{en} / {sw}" if en and sw else en or sw
    if queue_name and destination != RoutingDestination.FALLBACK_AI:
        return base
    return base


def escalation_ack(language: str = "mixed") -> str:
    if language == "sw":
        return _ESCALATION_ACK_SW
    if language == "en":
        return _ESCALATION_ACK_EN
    return f"{_ESCALATION_ACK_EN} / {_ESCALATION_ACK_SW}"


def callback_offer(language: str = "mixed") -> str:
    if language == "sw":
        return _CALLBACK_OFFER_SW
    if language == "en":
        return _CALLBACK_OFFER_EN
    return f"{_CALLBACK_OFFER_EN} / {_CALLBACK_OFFER_SW}"
