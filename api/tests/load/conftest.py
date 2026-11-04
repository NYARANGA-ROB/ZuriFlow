"""Pytest configuration for load/reliability tests."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "load: load and stress tests (may be slow)")
    config.addinivalue_line("markers", "reliability: workflow reliability tests")
    config.addinivalue_line(
        "markers",
        "live_load: requires running API (set LOAD_TEST_WS_URL)",
    )


@pytest.fixture
def live_ws_url() -> str | None:
    return os.getenv("LOAD_TEST_WS_URL")
