from __future__ import annotations

from api.enums import ToolCategory
from api.utils.url_security import validate_user_configured_service_url

PRIVILEGED_CATEGORIES = frozenset(
    {
        ToolCategory.HTTP_API.value,
        ToolCategory.MCP.value,
        ToolCategory.TRANSFER_CALL.value,
        ToolCategory.INTEGRATION.value,
    }
)

SAFE_RUNTIME_CATEGORIES = frozenset(
    {
        ToolCategory.END_CALL.value,
        ToolCategory.CALCULATOR.value,
        ToolCategory.SEND_DTMF.value,
        ToolCategory.NATIVE.value,
    }
)


class ToolPolicyDenied(PermissionError):
    pass


def authorize_runtime_tool(*, category: str, name: str) -> None:
    if category in SAFE_RUNTIME_CATEGORIES:
        return
    if category not in PRIVILEGED_CATEGORIES:
        raise ToolPolicyDenied(f"Tool category '{category}' is not allowed at runtime")
    if not name or name.startswith("_"):
        raise ToolPolicyDenied("Anonymous or internal tools cannot be invoked by the model")


def authorize_http_tool_url(url: str) -> None:
    if not url:
        raise ToolPolicyDenied("HTTP tool is missing a URL")
    lowered = url.strip().lower()
    if lowered.startswith(("file:", "javascript:", "data:")):
        raise ToolPolicyDenied("HTTP tool URL scheme is not allowed")
    validate_user_configured_service_url(url, field_name="tool.url")
