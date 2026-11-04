"""Data classification for least-privilege reviews. Not a compliance attestation."""

from __future__ import annotations

from enum import Enum

from api.services.tenant.types import Permission


class DataClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


CLASSIFICATION = {
    "phone_numbers": DataClass.RESTRICTED,
    "recordings": DataClass.RESTRICTED,
    "transcripts": DataClass.RESTRICTED,
    "payment_information": DataClass.RESTRICTED,
    "api_credentials": DataClass.RESTRICTED,
    "customer_information": DataClass.CONFIDENTIAL,
    "analytics_aggregates": DataClass.INTERNAL,
    "workflow_graphs": DataClass.INTERNAL,
}


LEAST_PRIVILEGE_PERMISSIONS = {
    "phone_numbers": Permission.CONVERSATION_PII_READ,
    "recordings": Permission.RECORDING_READ,
    "transcripts": Permission.TRANSCRIPT_READ,
    "payment_information": Permission.PAYMENT_ANALYTICS_READ,
    "api_credentials": Permission.API_KEY_READ,
    "customer_information": Permission.CONVERSATION_PII_READ,
}
