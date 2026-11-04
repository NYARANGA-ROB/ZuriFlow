"""Hand-written SDK client for the Dograh public API platform.

Generated SDK methods (``get_platform_info``, ``trigger_voice_call``, etc.) live in
``_generated_client.py`` after running ``scripts/generate_sdk.sh``. This module
provides a focused developer surface for webhooks, usage analytics, and voice
call triggers without waiting for codegen.
"""

from __future__ import annotations

from typing import Any

import httpx

from .errors import ApiError


class PlatformClient:
    """Developer-friendly client for ``/api/v1/platform`` endpoints."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self._http = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/api/v1/platform",
            headers=headers,
            timeout=timeout,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> PlatformClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def info(self) -> dict[str, Any]:
        return self._request("GET", "")

    def routes(self) -> list[dict[str, Any]]:
        return self._request("GET", "/routes")

    def usage(self, *, scope: str = "organization") -> dict[str, Any]:
        return self._request("GET", "/usage", params={"scope": scope})

    def list_webhooks(self) -> list[dict[str, Any]]:
        return self._request("GET", "/webhooks")

    def create_webhook(
        self,
        *,
        name: str,
        url: str,
        events: list[str],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/webhooks",
            json={"name": name, "url": url, "events": events},
        )

    def test_webhook(self, subscription_uuid: str) -> dict[str, Any]:
        return self._request("POST", f"/webhooks/{subscription_uuid}/test")

    def trigger_call(
        self,
        trigger_path: str,
        *,
        phone_number: str,
        initial_context: dict[str, Any] | None = None,
        telephony_configuration_id: int | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/calls/trigger/{trigger_path}",
            json={
                "phone_number": phone_number,
                "initial_context": initial_context,
                "telephony_configuration_id": telephony_configuration_id,
            },
        )

    def trigger_call_by_workflow(
        self,
        workflow_uuid: str,
        *,
        phone_number: str,
        initial_context: dict[str, Any] | None = None,
        telephony_configuration_id: int | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/calls/workflow/{workflow_uuid}",
            json={
                "phone_number": phone_number,
                "initial_context": initial_context,
                "telephony_configuration_id": telephony_configuration_id,
            },
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("detail") if isinstance(body, dict) else response.text
            except ValueError:
                body = response.text
                message = response.text
            raise ApiError(response.status_code, message, body=body)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()
