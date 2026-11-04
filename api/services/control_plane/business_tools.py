"""No-code business tool templates that create real organization tools."""

from __future__ import annotations

from api.db.models import UserModel
from api.enums import ToolCategory
from api.schemas.tool import (
    CreateToolRequest,
    HttpApiConfig,
    HttpApiToolDefinition,
    ToolParameter,
    TransferCallConfig,
    TransferCallToolDefinition,
)
from api.services.control_plane.audit import INTEGRATION_ADDED, log_admin_action
from api.services.tool_management import create_tool_for_user

BUSINESS_TOOL_CATALOG = [
    {
        "key": "appointment_booking",
        "name": "Book appointment",
        "description": "Schedule a customer appointment in the business calendar.",
        "kind": "http",
        "method": "POST",
        "url": "https://example.co.ke/api/appointments",
        "parameters": [
            {"name": "customer_name", "type": "string", "description": "Customer name", "required": True},
            {"name": "datetime", "type": "string", "description": "ISO datetime", "required": True},
        ],
    },
    {
        "key": "order_lookup",
        "name": "Lookup order",
        "description": "Find an order by reference number.",
        "kind": "http",
        "method": "GET",
        "url": "https://example.co.ke/api/orders",
        "parameters": [
            {"name": "order_id", "type": "string", "description": "Order reference", "required": True},
        ],
    },
    {
        "key": "customer_lookup",
        "name": "Lookup customer",
        "description": "Find a customer by phone number.",
        "kind": "http",
        "method": "GET",
        "url": "https://example.co.ke/api/customers",
        "parameters": [
            {"name": "phone", "type": "string", "description": "Kenyan phone number", "required": True},
        ],
    },
    {
        "key": "payment",
        "name": "Request payment",
        "description": "Start an M-Pesa or card payment for the customer.",
        "kind": "http",
        "method": "POST",
        "url": "https://example.co.ke/api/payments",
        "parameters": [
            {"name": "amount", "type": "string", "description": "Amount in KES", "required": True},
            {"name": "phone", "type": "string", "description": "Paying phone", "required": True},
        ],
    },
    {
        "key": "delivery_tracking",
        "name": "Track delivery",
        "description": "Look up a shipment or delivery status.",
        "kind": "http",
        "method": "GET",
        "url": "https://example.co.ke/api/deliveries",
        "parameters": [
            {"name": "tracking_id", "type": "string", "description": "Tracking code", "required": True},
        ],
    },
    {
        "key": "crm_lookup",
        "name": "CRM lookup",
        "description": "Fetch the customer record from CRM.",
        "kind": "http",
        "method": "GET",
        "url": "https://example.co.ke/api/crm",
        "parameters": [
            {"name": "phone", "type": "string", "description": "Customer phone", "required": True},
        ],
    },
    {
        "key": "ticket_creation",
        "name": "Create support ticket",
        "description": "Open a follow-up ticket for the customer.",
        "kind": "http",
        "method": "POST",
        "url": "https://example.co.ke/api/tickets",
        "parameters": [
            {"name": "subject", "type": "string", "description": "Ticket subject", "required": True},
            {"name": "details", "type": "string", "description": "Issue details", "required": False},
        ],
    },
    {
        "key": "human_transfer",
        "name": "Transfer to human",
        "description": "Warm-transfer the call to an escalation contact.",
        "kind": "transfer",
    },
    {
        "key": "sms",
        "name": "Send SMS",
        "description": "Send an SMS follow-up to the customer.",
        "kind": "http",
        "method": "POST",
        "url": "https://example.co.ke/api/sms",
        "parameters": [
            {"name": "phone", "type": "string", "description": "Recipient phone", "required": True},
            {"name": "message", "type": "string", "description": "SMS body", "required": True},
        ],
    },
    {
        "key": "whatsapp",
        "name": "Send WhatsApp",
        "description": "Send a WhatsApp follow-up to the customer.",
        "kind": "http",
        "method": "POST",
        "url": "https://example.co.ke/api/whatsapp",
        "parameters": [
            {"name": "phone", "type": "string", "description": "Recipient phone", "required": True},
            {"name": "message", "type": "string", "description": "WhatsApp body", "required": True},
        ],
    },
]


def list_business_tools() -> list[dict]:
    return [
        {
            "key": item["key"],
            "name": item["name"],
            "description": item["description"],
            "kind": item["kind"],
        }
        for item in BUSINESS_TOOL_CATALOG
    ]


async def install_business_tool(
    *,
    user: UserModel,
    key: str,
    endpoint_url: str | None = None,
    transfer_destination: str | None = None,
) -> dict:
    item = next((t for t in BUSINESS_TOOL_CATALOG if t["key"] == key), None)
    if item is None:
        raise ValueError(f"Unknown business tool '{key}'")

    if item["kind"] == "transfer":
        destination = transfer_destination or ""
        request = CreateToolRequest(
            name=item["name"],
            description=item["description"],
            category=ToolCategory.TRANSFER_CALL.value,
            definition=TransferCallToolDefinition(
                type="transfer_call",
                config=TransferCallConfig(destination=destination),
            ),
        )
    else:
        params = [
            ToolParameter(
                name=p["name"],
                type=p["type"],
                description=p["description"],
                required=p.get("required", True),
            )
            for p in item.get("parameters", [])
        ]
        request = CreateToolRequest(
            name=item["name"],
            description=item["description"],
            category=ToolCategory.HTTP_API.value,
            definition=HttpApiToolDefinition(
                type="http_api",
                config=HttpApiConfig(
                    method=item["method"],
                    url=endpoint_url or item["url"],
                    parameters=params,
                ),
            ),
        )

    tool = await create_tool_for_user(request, user, source="control_plane")
    await log_admin_action(
        organization_id=user.selected_organization_id,
        action=INTEGRATION_ADDED,
        resource_type="tool",
        actor_user_id=user.id,
        resource_id=getattr(tool, "tool_uuid", None) or str(getattr(tool, "id", "")),
        summary=f"Installed business tool {item['name']}",
        metadata={"key": key},
    )
    return tool.model_dump() if hasattr(tool, "model_dump") else dict(tool)
