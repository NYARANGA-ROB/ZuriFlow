"""Pydantic schemas for realtime conversation memory API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryEventRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    user_text: str | None = None
    assistant_text: str | None = None
    interrupted: bool = False
    partial_assistant: str = ""


class RetrieveRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)


class RetrievalResponse(BaseModel):
    result: dict[str, Any]


class SnapshotResponse(BaseModel):
    snapshot: dict[str, Any]
