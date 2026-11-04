"""Tests for Fernet credential encryption at rest."""

from unittest.mock import patch

from api.utils.credential_encryption import (
    ENCRYPTION_WRAPPER_KEY,
    decrypt_credential_data,
    encrypt_credential_data,
    generate_encryption_key,
    is_encrypted_credential_data,
)


def test_round_trip_encrypt_decrypt():
    key = generate_encryption_key()
    payload = {"token": "super-secret", "header_name": "Authorization"}

    with patch("api.utils.credential_encryption.CREDENTIAL_ENCRYPTION_ENABLED", True):
        with patch("api.utils.credential_encryption.CREDENTIAL_ENCRYPTION_KEY", key):
            encrypted = encrypt_credential_data(payload)
            assert is_encrypted_credential_data(encrypted)
            assert ENCRYPTION_WRAPPER_KEY in encrypted
            assert "super-secret" not in str(encrypted)

            decrypted = decrypt_credential_data(encrypted)
            assert decrypted == payload


def test_passthrough_when_disabled():
    payload = {"api_key": "plain"}
    with patch("api.utils.credential_encryption.CREDENTIAL_ENCRYPTION_ENABLED", False):
        assert encrypt_credential_data(payload) == payload
        assert decrypt_credential_data(payload) == payload
