"""Public API authentication helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request

from api.db import db_client
from api.services.public_api.types import PublicApiContext


async def resolve_public_api_context(raw_api_key: str) -> PublicApiContext:
    api_key = await db_client.validate_api_key(raw_api_key)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    if not api_key.created_by:
        raise HTTPException(status_code=401, detail="API key has no associated user")
    return PublicApiContext(
        organization_id=api_key.organization_id,
        api_key_id=api_key.id,
        api_key_prefix=api_key.key_prefix,
        created_by_user_id=api_key.created_by,
    )


async def get_public_api_context(request: Request) -> PublicApiContext:
    """Read context set by PublicApiGatewayMiddleware, or validate header."""
    cached = getattr(request.state, "public_api_context", None)
    if cached is not None:
        return cached

    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail="X-API-Key header required",
        )
    ctx = await resolve_public_api_context(raw_key)
    request.state.public_api_context = ctx
    return ctx


async def get_public_api_context_header(
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
) -> PublicApiContext:
    return await resolve_public_api_context(x_api_key)
