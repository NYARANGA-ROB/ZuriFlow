"""Extract Kenyan business entities from a caller utterance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from api.services.kenya.currency import parse_kes
from api.services.kenya.phone import normalize_kenyan_phone

# Safaricom M-Pesa codes are typically 10 alphanumeric chars (e.g. QH45XYZ123).
_MPESA_CODE = re.compile(r"\b([A-Z0-9]{10})\b")
_ORDER = re.compile(
    r"\b(?:order|oda)\s*(?:number|no\.?|#)?\s*[:#]?\s*([A-Z0-9-]{4,20})\b",
    re.I,
)
_ACCOUNT = re.compile(
    r"\b(?:account|acc(?:ount)?|akaunti|ref(?:erence)?)\s*(?:number|no\.?)?\s*[:#]?\s*([A-Z0-9-]{3,24})\b",
    re.I,
)
_NATIONAL_ID = re.compile(
    r"\b(?:national\s*id|id\s*number|kitambulisho|namba\s*ya\s*id)\s*[:#]?\s*(\d{5,8})\b",
    re.I,
)
_DATE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|today|leo|tomorrow|kesho|jana|yesterday)\b",
    re.I,
)
_TIME = re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|asubuhi|jioni|usiku)?)\b", re.I)
_NAME = re.compile(
    r"\b(?:my name is|jina langu ni|nitaitwa|i am|nina)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b",
    re.I,
)
_LOCATION_HINTS = (
    "estate",
    "town",
    "county",
    "nairobi",
    "mombasa",
    "kisumu",
    "nakuru",
    "eldoret",
    "thika",
    "kitengela",
    "kasarani",
    "westlands",
    "eastleigh",
    "kibera",
    "kayole",
    "ruiru",
    "syokimau",
    "ngong",
    "kikuyu",
    "kiambu",
    "machakos",
    "kisii",
    "kakamega",
    "meru",
    "nyeri",
)


@dataclass
class ExtractedEntities:
    phone: dict[str, Any] | None = None
    customer_name: str | None = None
    amount_kes: dict[str, Any] | None = None
    mpesa_transaction_code: str | None = None
    date: str | None = None
    time: str | None = None
    location: str | None = None
    estate: str | None = None
    town: str | None = None
    county: str | None = None
    order_number: str | None = None
    account_number: str | None = None
    national_id_ref: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        """Workflow-facing payload. National ID is redacted."""
        data: dict[str, Any] = {
            "phone": self.phone,
            "customer_name": self.customer_name,
            "amount_kes": self.amount_kes,
            "mpesa_transaction_code": self.mpesa_transaction_code,
            "date": self.date,
            "time": self.time,
            "location": self.location,
            "estate": self.estate,
            "town": self.town,
            "county": self.county,
            "order_number": self.order_number,
            "account_number": self.account_number,
        }
        if self.national_id_ref:
            data["national_id_ref"] = _redact_id(self.national_id_ref)
            data["national_id_present"] = True
        return {k: v for k, v in data.items() if v is not None}


def extract_kenyan_entities(text: str) -> ExtractedEntities:
    entities = ExtractedEntities()
    if not text:
        return entities

    phone_match = re.search(
        r"(?:\+?254|0)(?:7|1)\d{8}\b|\+254\d{9}\b",
        text,
    )
    if phone_match:
        parsed = normalize_kenyan_phone(phone_match.group(0))
        if parsed.valid:
            entities.phone = parsed.to_dict()

    kes = parse_kes(_amount_span(text))
    if kes.valid:
        entities.amount_kes = kes.to_dict()

    mpesa = next(
        (
            m.group(1)
            for m in _MPESA_CODE.finditer(text.upper())
            if any(ch.isalpha() for ch in m.group(1)) and any(ch.isdigit() for ch in m.group(1))
        ),
        None,
    )
    if mpesa:
        entities.mpesa_transaction_code = mpesa

    name = _NAME.search(text)
    if name:
        entities.customer_name = name.group(1).strip()

    date_m = _DATE.search(text)
    if date_m:
        entities.date = date_m.group(1)

    time_m = _TIME.search(text)
    if time_m:
        entities.time = time_m.group(1).strip()

    order = _ORDER.search(text)
    if order:
        entities.order_number = order.group(1)

    account = _ACCOUNT.search(text)
    if account:
        entities.account_number = account.group(1)

    nid = _NATIONAL_ID.search(text)
    if nid:
        entities.national_id_ref = nid.group(1)

    lowered = text.lower()
    for hint in _LOCATION_HINTS:
        if hint in lowered:
            entities.location = hint.title() if hint not in {"estate", "town", "county"} else entities.location
            if hint == "estate":
                estate = re.search(r"\b([A-Za-z]{3,20})\s+estate\b", text, re.I)
                if estate:
                    entities.estate = estate.group(0)
            elif hint in {"nairobi", "mombasa", "kisumu", "nakuru", "eldoret", "thika"}:
                entities.town = hint.title()
            elif hint in {"kiambu", "machakos", "kisii", "kakamega", "meru", "nyeri"}:
                entities.county = hint.title()
    return entities


def _amount_span(text: str) -> str:
    match = re.search(
        r"(\d[\d,]*(?:\.\d+)?\s*(?:k|kes|ksh|bob|shillings?|shilingi)?|"
        r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|twenty|thirty|forty|fifty|hundred|thousand|"
        r"mia|elfu)(?:\s+\w+){0,6})",
        text,
        re.I,
    )
    return match.group(0) if match else text


def _redact_id(value: str) -> str:
    if len(value) <= 3:
        return "***"
    return f"{'*' * (len(value) - 3)}{value[-3:]}"
