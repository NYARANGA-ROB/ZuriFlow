"""
Africa's Talking implementation of the TelephonyProvider interface.

Outbound calls use the AT Voice REST API. Inbound and answer callbacks return
XML with a bidirectional ``Stream`` element (Plivo-compatible framing) for
real-time AI when your AT account is configured with a SIP/media gateway that
supports streaming. Callback URLs are set in the Africa's Talking voice console.
"""

import json
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiohttp
from fastapi import HTTPException
from loguru import logger

from api.db import db_client
from api.enums import WorkflowRunMode
from api.services.telephony.base import (
    CallInitiationResult,
    NormalizedInboundData,
    TelephonyProvider,
)
from api.services.telephony.ws_connect import build_telephony_websocket_url_for_run
from api.utils.common import get_backend_endpoints
from api.utils.telephony_address import normalize_telephony_address

if TYPE_CHECKING:
    from fastapi import WebSocket

VOICE_API_BASE = "https://voice.africastalking.com"


class AfricasTalkingProvider(TelephonyProvider):
    """Africa's Talking telephony provider."""

    PROVIDER_NAME = WorkflowRunMode.AFRICASTALKING.value
    WEBHOOK_ENDPOINT = "africastalking-xml"

    def __init__(self, config: Dict[str, Any]):
        self.username = config.get("username")
        self.api_key = config.get("api_key")
        self.from_numbers = config.get("from_numbers", [])

        if isinstance(self.from_numbers, str):
            self.from_numbers = [self.from_numbers]

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        from_number: Optional[str] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        if not self.validate_config():
            raise ValueError("Africa's Talking provider not properly configured")

        if from_number is None:
            from_number = random.choice(self.from_numbers)

        data = {
            "username": self.username,
            "from": from_number,
            "to": to_number,
        }
        if workflow_run_id:
            data["clientRequestId"] = str(workflow_run_id)

        data.update(kwargs)

        headers = {
            "apiKey": self.api_key,
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{VOICE_API_BASE}/call",
                data=data,
                headers=headers,
            ) as response:
                response_text = await response.text()
                if response.status not in (200, 201, 202):
                    raise HTTPException(
                        status_code=response.status,
                        detail=(
                            "Failed to initiate Africa's Talking call: "
                            f"{response_text}"
                        ),
                    )

                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "Africa's Talking response was not valid JSON: "
                            f"{response_text}"
                        ),
                    )

                entries = response_data.get("entries") or []
                first_entry = entries[0] if entries else response_data
                call_id = first_entry.get("sessionId") or first_entry.get("session_id")

                if not call_id:
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "Africa's Talking response missing sessionId: "
                            f"{response_data}"
                        ),
                    )

                return CallInitiationResult(
                    call_id=call_id,
                    status=first_entry.get("status", "queued"),
                    caller_number=from_number,
                    provider_metadata={"session_id": call_id},
                    raw_response=response_data,
                )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        return {
            "sessionId": call_id,
            "status": "unknown",
            "note": "Africa's Talking does not expose a per-session REST status endpoint",
        }

    async def get_available_phone_numbers(self) -> List[str]:
        return self.from_numbers

    def validate_config(self) -> bool:
        return bool(self.username and self.api_key and self.from_numbers)

    async def verify_webhook_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        # Africa's Talking Voice API does not document signed webhooks.
        return True

    async def get_webhook_response(
        self, workflow_id: int, user_id: int, workflow_run_id: int
    ) -> str:
        stream_url = await build_telephony_websocket_url_for_run(
            workflow_id, user_id, workflow_run_id
        )

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">{stream_url}</Stream>
</Response>"""

    async def get_call_cost(self, call_id: str) -> Dict[str, Any]:
        return {
            "cost_usd": 0.0,
            "duration": 0,
            "status": "unknown",
            "note": "Africa's Talking cost must be reconciled from AT dashboard exports",
        }

    def parse_status_callback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        status_map = {
            "ringing": "ringing",
            "active": "answered",
            "completed": "completed",
            "failed": "failed",
            "busy": "busy",
            "no-answer": "no-answer",
            "noanswer": "no-answer",
        }

        call_status = (data.get("callSessionState") or data.get("status") or "").lower()
        duration = data.get("durationInSeconds") or data.get("duration")
        return {
            "call_id": data.get("sessionId", ""),
            "status": status_map.get(call_status, call_status or "unknown"),
            "from_number": data.get("callerNumber") or data.get("from"),
            "to_number": data.get("destinationNumber") or data.get("to"),
            "direction": data.get("direction"),
            "duration": duration,
            "extra": data,
        }

    async def handle_websocket(
        self,
        websocket: "WebSocket",
        workflow_id: int,
        user_id: int,
        workflow_run_id: int,
    ) -> None:
        from api.services.pipecat.run_pipeline import run_pipeline_telephony

        first_msg = await websocket.receive_text()
        start_msg = json.loads(first_msg)

        if start_msg.get("event") != "start":
            logger.error(f"Expected 'start' event, got: {start_msg.get('event')}")
            await websocket.close(code=4400, reason="Expected start event")
            return

        start_data = start_msg.get("start", {})
        stream_id = start_data.get("streamId") or start_msg.get("streamId")

        if not stream_id:
            logger.error(f"Missing streamId in start event: {start_msg}")
            await websocket.close(code=4400, reason="Missing streamId")
            return

        workflow_run = await db_client.get_workflow_run(workflow_run_id)
        call_id = None
        if workflow_run and workflow_run.gathered_context:
            call_id = workflow_run.gathered_context.get("call_id")

        if not call_id:
            call_id = (
                start_data.get("callId")
                or start_data.get("callUUID")
                or start_data.get("sessionId")
            )

        if not call_id:
            logger.error(
                f"Missing call ID for Africa's Talking workflow run {workflow_run_id}"
            )
            await websocket.close(code=4400, reason="Missing call ID")
            return

        await run_pipeline_telephony(
            websocket,
            provider_name=self.PROVIDER_NAME,
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            call_id=call_id,
            transport_kwargs={"stream_id": stream_id, "call_id": call_id},
        )

    @classmethod
    def can_handle_webhook(
        cls, webhook_data: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return "sessionId" in webhook_data and (
            "callerNumber" in webhook_data or "destinationNumber" in webhook_data
        )

    @staticmethod
    def parse_inbound_webhook(webhook_data: Dict[str, Any]) -> NormalizedInboundData:
        from_raw = webhook_data.get("callerNumber", "")
        to_raw = webhook_data.get("destinationNumber", "")
        return NormalizedInboundData(
            provider=AfricasTalkingProvider.PROVIDER_NAME,
            call_id=webhook_data.get("sessionId", ""),
            from_number=normalize_telephony_address(from_raw).canonical
            if from_raw
            else "",
            to_number=normalize_telephony_address(to_raw).canonical if to_raw else "",
            direction=webhook_data.get("direction", ""),
            call_status=webhook_data.get("callSessionState", ""),
            account_id=webhook_data.get("username"),
            raw_data=webhook_data,
        )

    @staticmethod
    def validate_account_id(config_data: dict, webhook_account_id: str) -> bool:
        if webhook_account_id:
            return config_data.get("username") == webhook_account_id
        return bool(config_data.get("username"))

    async def verify_inbound_signature(
        self,
        url: str,
        webhook_data: Dict[str, Any],
        headers: Dict[str, str],
        body: str = "",
    ) -> bool:
        # Africa's Talking Voice API does not document HMAC webhook signing.
        # Restrict exposure via network controls and console callback URL config.
        return True

    async def start_inbound_stream(
        self,
        *,
        websocket_url: str,
        workflow_run_id: int,
        normalized_data,
        backend_endpoint: str,
    ):
        from fastapi import Response

        hangup_callback_attr = ""
        if workflow_run_id:
            hangup_url = (
                f"{backend_endpoint}/api/v1/telephony/"
                f"africastalking/hangup-callback/{workflow_run_id}"
            )
            hangup_callback_attr = (
                f' statusCallbackUrl="{hangup_url}" statusCallbackMethod="POST"'
            )

        at_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000"{hangup_callback_attr}>{websocket_url}</Stream>
</Response>"""
        return Response(content=at_xml, media_type="application/xml")

    @staticmethod
    def generate_error_response(error_type: str, message: str) -> tuple:
        from fastapi import Response

        at_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, there was an error processing your call. {message}</Say>
    <Reject/>
</Response>"""
        return Response(content=at_xml, media_type="application/xml")

    @staticmethod
    def generate_validation_error_response(error_type) -> tuple:
        from fastapi import Response

        from api.errors.telephony_errors import TELEPHONY_ERROR_MESSAGES, TelephonyError

        message = TELEPHONY_ERROR_MESSAGES.get(
            error_type, TELEPHONY_ERROR_MESSAGES[TelephonyError.GENERAL_AUTH_FAILED]
        )

        at_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{message}</Say>
    <Reject/>
</Response>"""
        return Response(content=at_xml, media_type="application/xml")

    async def transfer_call(
        self,
        destination: str,
        transfer_id: str,
        conference_name: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "Africa's Talking provider does not support call transfers"
        )

    def supports_transfers(self) -> bool:
        return False
