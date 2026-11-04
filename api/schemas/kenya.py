"""Kenya market API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KenyaPhoneRequest(BaseModel):
    phone: str = Field(..., min_length=1, max_length=32)


class KenyaCurrencyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)


class KenyaLocalizeRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=4000)
    session_id: str = "kenya"
    style: str | None = None
    region: str | None = None


class KenyaConfirmKesRequest(BaseModel):
    text: str
    confirmed_amount: float


class KenyaPhraseCreate(BaseModel):
    phrase: str = Field(..., min_length=1, max_length=200)
    meaning: str = Field(..., min_length=1, max_length=500)
    language: str = "sheng"
    intent: str | None = None
    confidence: float = 0.85
    context: str | None = None
    region: str = "national"
    version: str = "1"
    is_active: bool = True
    global_phrase: bool = False


class KenyaPhraseUpdate(BaseModel):
    meaning: str | None = None
    language: str | None = None
    intent: str | None = None
    confidence: float | None = None
    context: str | None = None
    region: str | None = None
    version: str | None = None
    is_active: bool | None = None
