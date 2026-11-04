#!/usr/bin/env python3
"""Wrapper script — run from repo root."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.load_test.realtime_voice.__main__ import main

if __name__ == "__main__":
    main()
