from __future__ import annotations

from dataclasses import dataclass

from api.services.kenyan_intent.types import BusinessIntent

SWAHILI_MARKERS = frozenset(
    {
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
        "simu",
        "piga",
        "rudia",
    }
)


@dataclass(frozen=True)
class IntentPattern:
    phrase: str
    weight: float
    language: str = "mixed"


INTENT_PATTERNS: dict[BusinessIntent, tuple[IntentPattern, ...]] = {
    BusinessIntent.PAYMENT: (
        IntentPattern("pay", 0.82, "en"),
        IntentPattern("payment", 0.88, "en"),
        IntentPattern("send money", 0.9, "en"),
        IntentPattern("mpesa", 0.92, "mixed"),
        IntentPattern("m-pesa", 0.92, "mixed"),
        IntentPattern("lipa", 0.9, "sw"),
        IntentPattern("kulipa", 0.88, "sw"),
        IntentPattern("nataka kulipa", 0.93, "sw"),
        IntentPattern("pay bill", 0.87, "en"),
        IntentPattern("tuma pesa", 0.9, "sw"),
        IntentPattern("stk push", 0.91, "mixed"),
        IntentPattern("buy", 0.7, "en"),
        IntentPattern("purchase", 0.75, "en"),
        IntentPattern("invoice", 0.78, "en"),
    ),
    BusinessIntent.BALANCE_INQUIRY: (
        IntentPattern("balance", 0.9, "en"),
        IntentPattern("salio", 0.92, "sw"),
        IntentPattern("nataka balance", 0.94, "mixed"),
        IntentPattern("check balance", 0.93, "en"),
        IntentPattern("how much do i have", 0.86, "en"),
        IntentPattern("pesa yangu", 0.84, "sw"),
    ),
    BusinessIntent.BOOKING: (
        IntentPattern("book an appointment", 0.95, "en"),
        IntentPattern("book", 0.86, "en"),
        IntentPattern("booking", 0.88, "en"),
        IntentPattern("appointment", 0.9, "en"),
        IntentPattern("schedule", 0.84, "en"),
        IntentPattern("reserve", 0.82, "en"),
        IntentPattern("miadi", 0.9, "sw"),
        IntentPattern("weka miadi", 0.93, "sw"),
        IntentPattern("nataka miadi", 0.92, "sw"),
        IntentPattern("tarehe", 0.75, "sw"),
        IntentPattern("confirm appointment", 0.91, "en"),
        IntentPattern("reschedule", 0.85, "en"),
        IntentPattern("badilisha miadi", 0.88, "sw"),
    ),
    BusinessIntent.APPOINTMENT: (
        IntentPattern("appointment", 0.92, "en"),
        IntentPattern("miadi", 0.91, "sw"),
        IntentPattern("clinic", 0.8, "en"),
        IntentPattern("daktari", 0.84, "sw"),
    ),
    BusinessIntent.DELIVERY: (
        IntentPattern("delivery", 0.92, "en"),
        IntentPattern("deliver", 0.88, "en"),
        IntentPattern("courier", 0.86, "en"),
        IntentPattern("parcel", 0.85, "en"),
        IntentPattern("tuma bidhaa", 0.9, "sw"),
        IntentPattern("delivery yangu", 0.91, "mixed"),
    ),
    BusinessIntent.ORDER: (
        IntentPattern("order", 0.9, "en"),
        IntentPattern("oda", 0.88, "sheng"),
        IntentPattern("my order", 0.92, "en"),
        IntentPattern("agizo", 0.86, "sw"),
    ),
    BusinessIntent.COMPLAINT: (
        IntentPattern("complaint", 0.92, "en"),
        IntentPattern("complain", 0.88, "en"),
        IntentPattern("ninalalamika", 0.9, "sw"),
        IntentPattern("malalamiko", 0.9, "sw"),
        IntentPattern("this is unacceptable", 0.86, "en"),
    ),
    BusinessIntent.ACCOUNT_INQUIRY: (
        IntentPattern("my account", 0.9, "en"),
        IntentPattern("akaunti", 0.88, "sw"),
        IntentPattern("account number", 0.91, "en"),
        IntentPattern("namba ya akaunti", 0.9, "sw"),
    ),
    BusinessIntent.LOCATION_INQUIRY: (
        IntentPattern("where are you", 0.9, "en"),
        IntentPattern("uko wapi", 0.92, "sw"),
        IntentPattern("location", 0.86, "en"),
        IntentPattern("directions", 0.85, "en"),
        IntentPattern("estate", 0.8, "en"),
        IntentPattern("county", 0.78, "en"),
    ),
    BusinessIntent.CANCELLATION: (
        IntentPattern("cancel my order", 0.96, "en"),
        IntentPattern("cancel", 0.92, "en"),
        IntentPattern("cancellation", 0.9, "en"),
        IntentPattern("sitisha", 0.9, "sw"),
        IntentPattern("futa oda", 0.88, "sheng"),
    ),
    BusinessIntent.CONFIRMATION: (
        IntentPattern("confirm", 0.88, "en"),
        IntentPattern("confirmation", 0.9, "en"),
        IntentPattern("ndio", 0.7, "sw"),
        IntentPattern("sawa nimekubali", 0.92, "sw"),
        IntentPattern("yes please", 0.8, "en"),
    ),
    BusinessIntent.ESCALATION: (
        IntentPattern("human", 0.9, "en"),
        IntentPattern("agent", 0.88, "en"),
        IntentPattern("representative", 0.87, "en"),
        IntentPattern("speak to someone", 0.92, "en"),
        IntentPattern("talk to someone", 0.9, "en"),
        IntentPattern("manager", 0.85, "en"),
        IntentPattern("supervisor", 0.86, "en"),
        IntentPattern("customer care", 0.88, "mixed"),
        IntentPattern("mtu", 0.78, "sw"),
        IntentPattern("msee", 0.8, "mixed"),
        IntentPattern("nataka mtu", 0.9, "sw"),
        IntentPattern("transfer me", 0.87, "en"),
        IntentPattern("escalate", 0.91, "en"),
    ),
    BusinessIntent.SUPPORT: (
        IntentPattern("help", 0.84, "en"),
        IntentPattern("support", 0.88, "en"),
        IntentPattern("problem", 0.82, "en"),
        IntentPattern("issue", 0.8, "en"),
        IntentPattern("not working", 0.86, "en"),
        IntentPattern("broken", 0.8, "en"),
        IntentPattern("saidia", 0.9, "sw"),
        IntentPattern("ninasumbuliwa", 0.88, "sw"),
        IntentPattern("kuna shida", 0.9, "sw"),
        IntentPattern("complaint", 0.85, "en"),
        IntentPattern("troubleshoot", 0.83, "en"),
        IntentPattern("account issue", 0.87, "en"),
    ),
    BusinessIntent.CALLBACK: (
        IntentPattern("call me back", 0.93, "en"),
        IntentPattern("callback", 0.92, "en"),
        IntentPattern("ring me", 0.86, "en"),
        IntentPattern("call back", 0.9, "en"),
        IntentPattern("piga simu", 0.85, "sw"),
        IntentPattern("nipigie", 0.9, "sw"),
        IntentPattern("rudia simu", 0.91, "sw"),
        IntentPattern("call later", 0.84, "en"),
        IntentPattern("baadaye", 0.75, "sw"),
        IntentPattern("when you can call", 0.82, "en"),
        IntentPattern("follow up call", 0.88, "en"),
    ),
}
