"""Tests for outbound DTMF sanitization."""

import pytest

from api.services.telephony.dtmf_outbound import _sanitize_digits


def test_sanitize_digits_accepts_valid_sequence():
    assert _sanitize_digits("12#*") == "12#*"


def test_sanitize_digits_rejects_empty():
    with pytest.raises(ValueError):
        _sanitize_digits("abc")
