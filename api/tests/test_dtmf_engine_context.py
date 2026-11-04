"""Tests for Pipecat engine DTMF gathered context."""

import pytest

from api.services.workflow.pipecat_engine import PipecatEngine


@pytest.mark.asyncio
async def test_handle_dtmf_digit_accumulates_digits():
    engine = PipecatEngine.__new__(PipecatEngine)
    engine._gathered_context = {}

    await engine.handle_dtmf_digit("1")
    await engine.handle_dtmf_digit("2")

    assert engine._gathered_context["dtmf_digits"] == "12"
    assert engine._gathered_context["last_dtmf_digit"] == "2"
