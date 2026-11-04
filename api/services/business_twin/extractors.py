"""Extract structured business fields from untrusted HTML/text. Data, not instructions."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from api.services.business_twin.types import UNTRUSTED_CONTENT_PREAMBLE

_HOUR = re.compile(
    r"(?:open(?:ing)?|close(?:s|ing)?|hours?)[:\s]+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    re.I,
)
_PHONE = re.compile(r"(?:\+?254|0)7\d{8}")
_PRICE = re.compile(r"(?:KES|KSh|Ksh)\s*([\d,]+(?:\.\d{2})?)", re.I)
_FAQ_Q = re.compile(r"(?:^|\n)\s*(?:q[:.]|faq[:]?)\s*(.+)", re.I)


def wrap_untrusted(text: str) -> str:
    return f"{UNTRUSTED_CONTENT_PREAMBLE}\n---\n{text[:20000]}\n---"


def strip_boilerplate(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<nav[^>]*>.*?</nav>", " ", text)
    text = re.sub(r"(?is)<footer[^>]*>.*?</footer>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_from_text(text: str, *, source_url: str | None = None) -> dict[str, Any]:
    phones = list(dict.fromkeys(_PHONE.findall(text)))
    prices = _PRICE.findall(text)
    hours = _HOUR.findall(text)
    faqs = [{"question": m.group(1).strip()[:300], "answer": ""} for m in _FAQ_Q.finditer(text)][:8]
    services: list[str] = []
    lowered = text.lower()
    for token in ("delivery", "consultation", "booking", "repair", "training"):
        if token in lowered:
            services.append(token)
    return {
        "phones": phones[:5],
        "prices": [{"label": "mentioned", "amount": p.replace(",", ""), "currency": "KES"} for p in prices[:10]],
        "hours_mentions": hours[:6],
        "services": services,
        "faqs": faqs,
        "source_url": source_url,
        "confidence": 0.72 if source_url else 0.65,
        "wrapped_excerpt": wrap_untrusted(text[:1500]),
    }


def extract_from_html(html: str, *, source_url: str | None = None) -> dict[str, Any]:
    return extract_from_text(strip_boilerplate(html), source_url=source_url)


def extract_tabular_csv(content: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content))
    rows: list[dict[str, str]] = []
    for i, row in enumerate(reader):
        if i >= 500:
            break
        rows.append({k: (v or "").strip() for k, v in row.items() if k})
    return rows


def classify_document(filename: str, mime: str | None) -> str:
    name = filename.lower()
    if "price" in name or "menu" in name:
        return "price_list"
    if "policy" in name:
        return "policy"
    if "brochure" in name or "catalogue" in name or "catalog" in name:
        return "catalogue"
    if mime in {
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return "spreadsheet"
    return "document"


ALLOWED_UPLOAD_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "text/plain",
        "application/msword",
    }
)

ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".doc"})
