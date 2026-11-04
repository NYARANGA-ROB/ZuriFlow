"""Document ingestion helpers. Uploads stay on existing MinIO/KB pipeline."""

from __future__ import annotations

import os
from typing import Any

from api.services.business_twin.extractors import (
    ALLOWED_EXTENSIONS,
    ALLOWED_UPLOAD_TYPES,
    classify_document,
    extract_from_text,
    extract_tabular_csv,
)


class UnsafeDocumentError(ValueError):
    pass


def validate_upload(*, filename: str, mime_type: str | None, size_bytes: int | None) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsafeDocumentError("This file type cannot be used as business information")
    if mime_type and mime_type not in ALLOWED_UPLOAD_TYPES and not mime_type.startswith("text/"):
        raise UnsafeDocumentError("This file type cannot be used as business information")
    if size_bytes is not None and size_bytes > 5 * 1024 * 1024:
        raise UnsafeDocumentError("File is too large")
    return classify_document(filename, mime_type)


def extract_document_payload(*, filename: str, mime_type: str | None, text: str) -> dict[str, Any]:
    kind = classify_document(filename, mime_type)
    if kind == "spreadsheet" or filename.lower().endswith(".csv"):
        return {
            "kind": kind,
            "rows": extract_tabular_csv(text),
            "status": "pending_review",
            "source_type": "uploaded_document",
        }
    extracted = extract_from_text(text)
    extracted["kind"] = kind
    extracted["status"] = "pending_review"
    extracted["source_type"] = "uploaded_document"
    return extracted
