"""Fernet encryption helpers for sensitive JSON fields stored at rest."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from api.constants import CREDENTIAL_ENCRYPTION_ENABLED, CREDENTIAL_ENCRYPTION_KEY

ENCRYPTION_WRAPPER_KEY = "_dograh_enc"

_fernet: Optional[Fernet] = None


def _get_fernet() -> Optional[Fernet]:
    global _fernet
    if not CREDENTIAL_ENCRYPTION_ENABLED:
        return None
    if _fernet is not None:
        return _fernet
    if not CREDENTIAL_ENCRYPTION_KEY:
        logger.warning(
            "CREDENTIAL_ENCRYPTION_ENABLED is true but CREDENTIAL_ENCRYPTION_KEY is unset"
        )
        return None
    try:
        _fernet = Fernet(CREDENTIAL_ENCRYPTION_KEY.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        logger.error(f"Invalid CREDENTIAL_ENCRYPTION_KEY: {exc}")
        return None
    return _fernet


def is_encrypted_credential_data(data: Optional[Dict[str, Any]]) -> bool:
    return bool(data and ENCRYPTION_WRAPPER_KEY in data)


def encrypt_credential_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Encrypt credential_data for DB storage. Plain passthrough when disabled."""
    payload = dict(data or {})
    if not payload:
        return {}
    if is_encrypted_credential_data(payload):
        return payload

    fernet = _get_fernet()
    if fernet is None:
        return payload

    token = fernet.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return {ENCRYPTION_WRAPPER_KEY: token.decode("ascii")}


def decrypt_credential_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Decrypt credential_data after reading from DB."""
    if not data:
        return {}
    if not is_encrypted_credential_data(data):
        return dict(data)

    fernet = _get_fernet()
    if fernet is None:
        logger.warning("Encrypted credential_data present but encryption is not configured")
        return {}

    token = data.get(ENCRYPTION_WRAPPER_KEY, "")
    try:
        plaintext = fernet.decrypt(token.encode("ascii"))
    except (InvalidToken, AttributeError, TypeError) as exc:
        logger.error(f"Failed to decrypt credential_data: {exc}")
        return {}

    try:
        decoded = json.loads(plaintext.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error(f"Decrypted credential_data is not valid JSON: {exc}")
        return {}

    if not isinstance(decoded, dict):
        logger.error("Decrypted credential_data is not a JSON object")
        return {}
    return decoded


def generate_encryption_key() -> str:
    """Generate a new Fernet key (for operator setup / docs)."""
    return Fernet.generate_key().decode("ascii")
