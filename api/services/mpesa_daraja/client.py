from __future__ import annotations

import asyncio
import base64
import time
from datetime import datetime
from typing import Any

import aiohttp
from loguru import logger

from api.services.http_sessions import get_shared_http_session
from api.services.kenya_production.resilience import daraja_circuit
from api.services.mpesa_daraja.config import MpesaDarajaConfig
from api.services.mpesa_daraja.retry import with_daraja_retry
from api.services.mpesa_daraja.types import DarajaToken, STKQueryResult
from api.services.kenya.phone import normalize_kenyan_phone
from api.utils.telephony_address import normalize_telephony_address


def _mpesa_phone(phone_e164: str) -> str:
    kenya = normalize_kenyan_phone(phone_e164)
    if kenya.valid and kenya.national:
        return f"254{kenya.national}"
    normalized = normalize_telephony_address(
        phone_e164, country_hint="KE"
    ).canonical.lstrip("+")
    if normalized.startswith("0"):
        return f"254{normalized[1:]}"
    if not normalized.startswith("254"):
        return f"254{normalized}"
    return normalized


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _password(shortcode: str, passkey: str, timestamp: str) -> str:
    raw = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


class DarajaClient:
    """Low-level Safaricom Daraja API client with OAuth token caching."""

    def __init__(self, config: MpesaDarajaConfig) -> None:
        self._config = config
        self._token: DarajaToken | None = None
        self._token_lock = asyncio.Lock()

    async def get_access_token(self) -> str:
        breaker = daraja_circuit()
        if not breaker.allow():
            raise RuntimeError("Daraja circuit open — backing off")
        async with self._token_lock:
            if self._token and self._token.expires_at > time.time() + 30:
                return self._token.access_token

            url = f"{self._config.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth = aiohttp.BasicAuth(self._config.consumer_key, self._config.consumer_secret)
            session = await get_shared_http_session()
            async with session.get(url, auth=auth) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    breaker.record_failure()
                    raise RuntimeError(
                        data.get("errorMessage") or data.get("error") or str(data)
                    )
                token = data.get("access_token")
                if not token:
                    breaker.record_failure()
                    raise RuntimeError("Daraja OAuth response missing access_token")
                expires_in = int(data.get("expires_in", 3599))
                self._token = DarajaToken(
                    access_token=token,
                    expires_at=time.time() + expires_in,
                )
                breaker.record_success()
                return token

    @with_daraja_retry
    async def stk_push(
        self,
        *,
        phone_e164: str,
        amount: float,
        account_reference: str,
        transaction_desc: str,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        token = await self.get_access_token()
        ts = _timestamp()
        payload = {
            "BusinessShortCode": self._config.shortcode,
            "Password": _password(self._config.shortcode, self._config.passkey, ts),
            "Timestamp": ts,
            "TransactionType": self._config.transaction_type,
            "Amount": int(amount),
            "PartyA": _mpesa_phone(phone_e164),
            "PartyB": self._config.shortcode,
            "PhoneNumber": _mpesa_phone(phone_e164),
            "CallBackURL": callback_url or self._config.stk_callback_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": transaction_desc[:13],
        }
        url = f"{self._config.base_url}/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        breaker = daraja_circuit()
        if not breaker.allow():
            return {"errorMessage": "Daraja circuit open", "ResponseCode": "503"}

        session = await get_shared_http_session()
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                breaker.record_failure()
                logger.warning("Daraja STK push HTTP {}: {}", response.status, data)
            else:
                breaker.record_success()
            return data if isinstance(data, dict) else {"raw": data}

    @with_daraja_retry
    async def stk_push_query(self, checkout_request_id: str) -> STKQueryResult:
        token = await self.get_access_token()
        ts = _timestamp()
        payload = {
            "BusinessShortCode": self._config.shortcode,
            "Password": _password(self._config.shortcode, self._config.passkey, ts),
            "Timestamp": ts,
            "CheckoutRequestID": checkout_request_id,
        }
        url = f"{self._config.base_url}/mpesa/stkpushquery/v1/query"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        breaker = daraja_circuit()
        if not breaker.allow():
            return STKQueryResult(success=False, result_desc="Daraja circuit open")

        session = await get_shared_http_session()
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                breaker.record_failure()
            else:
                breaker.record_success()
            if not isinstance(data, dict):
                return STKQueryResult(success=False, raw_response={"raw": data})

            result_code = data.get("ResultCode")
            if result_code is None and "errorCode" in data:
                return STKQueryResult(
                    success=False,
                    result_code=int(data.get("errorCode", -1)),
                    result_desc=str(data.get("errorMessage", "")),
                    raw_response=data,
                )

            code = int(result_code) if result_code is not None else -1
            return STKQueryResult(
                success=code == 0,
                result_code=code,
                result_desc=str(data.get("ResultDesc", "")),
                raw_response=data,
            )
