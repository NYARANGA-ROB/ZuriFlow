from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import HTTPException, Request

from api.services.mpesa_daraja.config import MpesaDarajaConfig
from api.services.mpesa_daraja.types import STKCallbackResult


def parse_stk_callback(payload: dict[str, Any]) -> STKCallbackResult:
    body = payload.get("Body") or payload
    stk = body.get("stkCallback") or body
    if not stk:
        raise ValueError("Invalid STK callback payload: missing stkCallback")

    metadata_items: dict[str, Any] = {}
    callback_meta = stk.get("CallbackMetadata") or {}
    for item in callback_meta.get("Item") or []:
        name = item.get("Name")
        if name:
            metadata_items[name] = item.get("Value")

    return STKCallbackResult(
        checkout_request_id=str(stk.get("CheckoutRequestID", "")),
        merchant_request_id=stk.get("MerchantRequestID"),
        result_code=int(stk.get("ResultCode", -1)),
        result_desc=str(stk.get("ResultDesc", "")),
        mpesa_receipt_number=metadata_items.get("MpesaReceiptNumber"),
        amount=float(metadata_items["Amount"]) if metadata_items.get("Amount") is not None else None,
        phone_number=str(metadata_items["PhoneNumber"]) if metadata_items.get("PhoneNumber") else None,
        transaction_date=str(metadata_items["TransactionDate"])
        if metadata_items.get("TransactionDate")
        else None,
        metadata_items=metadata_items,
        raw_payload=payload,
    )


async def validate_callback_request(
    request: Request,
    config: MpesaDarajaConfig,
    *,
    organization_id: int,
) -> dict[str, Any]:
    """Validate inbound Daraja callback and return parsed JSON body."""
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty callback body")

    if config.webhook_secret:
        signature = request.headers.get("x-mpesa-signature") or request.headers.get(
            "X-Mpesa-Signature"
        )
        if not signature or not _verify_hmac(body, config.webhook_secret, signature):
            raise HTTPException(status_code=401, detail="Invalid callback signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON callback") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Callback must be a JSON object")

    try:
        parsed = parse_stk_callback(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parsed.checkout_request_id:
        raise HTTPException(status_code=400, detail="Missing CheckoutRequestID")

    return payload


def verify_hmac_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, provided)


def _verify_hmac(body: bytes, secret: str, signature: str) -> bool:
    return verify_hmac_signature(body, secret, signature)
