from __future__ import annotations

from typing import Any

from loguru import logger

from api.db import db_client

LOGIN_SUCCESS = "login_success"
LOGIN_FAILURE = "login_failure"
LOGIN_LOCKOUT = "login_lockout"
MFA_ENABLED = "mfa_enabled"
MFA_DISABLED = "mfa_disabled"
TOKEN_REFRESH = "token_refresh"
TOKEN_REFRESH_REUSE = "token_refresh_reuse"
API_KEY_CREATED = "api_key_created"
TOOL_CREATED = "tool_created"
PRIVILEGED_TOOL_DENIED = "privileged_tool_denied"


async def log_security_event(
    *,
    action: str,
    resource_type: str,
    outcome: str = "success",
    organization_id: int | None = None,
    actor_user_id: int | None = None,
    resource_id: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await db_client.append_security_audit_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            summary=summary,
            metadata_json=metadata or {},
        )
    except Exception:
        logger.warning("Failed to persist security audit event {}", action, exc_info=True)
