"""One-time WebSocket connect tokens for telephony media streams."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from api.utils.common import get_backend_endpoints

if TYPE_CHECKING:
    from api.db.models import WorkflowRunModel


def generate_ws_connect_token() -> str:
    return secrets.token_urlsafe(32)


def ws_connect_token_from_run(workflow_run: WorkflowRunModel | None) -> str | None:
    if workflow_run is None:
        return None
    gathered = workflow_run.gathered_context or {}
    token = gathered.get("ws_connect_token")
    return str(token) if token else None


def validate_ws_connect_token(
    workflow_run: WorkflowRunModel | None,
    token: str | None,
) -> bool:
    expected = ws_connect_token_from_run(workflow_run)
    if not expected:
        return True
    if not token:
        return False
    return secrets.compare_digest(expected, token)


async def build_telephony_websocket_url(
    workflow_id: int,
    user_id: int,
    workflow_run_id: int,
    *,
    ws_connect_token: str | None = None,
) -> str:
    _, wss_backend_endpoint = await get_backend_endpoints()
    url = (
        f"{wss_backend_endpoint}/api/v1/telephony/ws/"
        f"{workflow_id}/{user_id}/{workflow_run_id}"
    )
    if ws_connect_token:
        url = f"{url}?token={ws_connect_token}"
    return url


async def build_telephony_websocket_url_for_run(
    workflow_id: int,
    user_id: int,
    workflow_run_id: int,
) -> str:
    from api.db import db_client

    run = await db_client.get_workflow_run(workflow_run_id)
    token = ws_connect_token_from_run(run)
    return await build_telephony_websocket_url(
        workflow_id,
        user_id,
        workflow_run_id,
        ws_connect_token=token,
    )

