"""Tests for telephony WebSocket connect tokens."""

from __future__ import annotations

import secrets
from types import SimpleNamespace

from api.services.telephony.ws_connect import (
    generate_ws_connect_token,
    validate_ws_connect_token,
    ws_connect_token_from_run,
)


def test_validate_ws_connect_token_allows_missing_token_on_legacy_runs():
    run = SimpleNamespace(gathered_context={})
    assert validate_ws_connect_token(run, None) is True


def test_validate_ws_connect_token_rejects_wrong_token():
    token = generate_ws_connect_token()
    run = SimpleNamespace(gathered_context={"ws_connect_token": token})
    assert validate_ws_connect_token(run, "wrong") is False
    assert validate_ws_connect_token(run, token) is True


def test_ws_connect_token_from_run():
    token = secrets.token_urlsafe(16)
    run = SimpleNamespace(gathered_context={"ws_connect_token": token})
    assert ws_connect_token_from_run(run) == token
