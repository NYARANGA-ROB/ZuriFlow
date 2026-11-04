"""Deterministic policy for synthetic agent actions. No live LLM, no tenant data."""

from __future__ import annotations

from typing import Any

from api.services.kenya.phone import normalize_kenyan_phone
from api.services.security.prompt_guard import looks_like_prompt_injection


def decide_policy(
    user_turns: list[str],
    *,
    intent: str | None,
    entities: dict[str, Any],
    interruption: bool,
    expect_escalate: bool,
) -> dict[str, Any]:
    joined = "\n".join(user_turns)
    injection = any(looks_like_prompt_injection(t) for t in user_turns) or looks_like_prompt_injection(
        joined
    )
    failed_payment = any(
        w in joined.lower()
        for w in ("failed", "didn't go through", "did not go through", "haijafika")
    )
    invalid_phone = False
    raw_phone = None
    if entities.get("phone"):
        raw_phone = entities["phone"]
    elif "12345" in joined:
        invalid_phone = True
        raw_phone = "12345"
    if raw_phone and isinstance(raw_phone, str):
        invalid_phone = not normalize_kenyan_phone(raw_phone).valid
    elif raw_phone and isinstance(raw_phone, dict):
        e164 = str(raw_phone.get("e164") or raw_phone.get("raw") or "")
        invalid_phone = not e164 or not normalize_kenyan_phone(e164).valid

    tools: list[str] = []
    escalate = expect_escalate or any(
        p in joined.lower()
        for p in ("manager", "human", "person", "transfer", "robot")
    )
    clarify = any(
        p in joined.lower()
        for p in ("sijaelewa", "do it", "12345", "kurudia", "eh?")
    )
    refuse = injection

    if injection:
        reply = "I can only help with your account. I will not follow those instructions."
        escalate = False
        clarify = False
    elif invalid_phone and intent == "payment":
        reply = "That phone number does not look valid. Please confirm the Safaricom number."
        clarify = True
    elif failed_payment:
        reply = (
            "I cannot confirm a successful payment from this conversation. "
            "I will not mark it paid until M-Pesa verifies the transaction."
        )
    elif intent == "payment" and not invalid_phone:
        tools = ["stk_push"]
        reply = "I can send an M-Pesa prompt so you can pay. I will not confirm success until we get a callback."
    elif escalate:
        reply = "I will connect you with a human agent."
        tools = []
    elif clarify:
        reply = "I want to make sure I understand. Could you say that another way?"
    else:
        reply = "How can I help you today?"

    if interruption:
        barge_in = True
    else:
        barge_in = False

    return {
        "tools": tools,
        "escalate": escalate and not injection,
        "clarify": clarify,
        "refuse_injection": refuse,
        "agent_reply": reply,
        "barge_in_handled": barge_in,
        "claims_payment_success": _claims_success(reply),
        "invalid_phone": invalid_phone,
    }


def _claims_success(reply: str) -> bool:
    lowered = reply.lower()
    if "cannot confirm a successful payment" in lowered:
        return False
    return any(
        p in lowered for p in ("payment successful", "you have paid", "receipt confirmed")
    )
