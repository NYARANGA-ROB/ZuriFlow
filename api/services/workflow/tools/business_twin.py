"""Agent tools that query the Digital Twin with tenant isolation."""

from __future__ import annotations

from api.services.workflow.pipecat_engine_custom_tools import get_function_schema

TOOL_SPECS = [
    ("get_business_hours", "Look up verified opening hours. Do not guess."),
    ("get_business_profile", "Look up what the business is and whether it accepts M-Pesa."),
    ("get_branch_information", "Look up branch locations and counties."),
    ("get_service", "List approved services the business offers."),
    ("get_product", "List approved product descriptions."),
    ("get_price", "Look up an approved price. Use live inventory for stock."),
    ("check_inventory", "Check live stock. Never use stale documents for stock."),
    ("check_appointment_availability", "Check the live booking calendar."),
    ("get_order_status", "Look up a live order."),
    ("get_delivery_status", "Look up live delivery status."),
    ("get_payment_status", "Look up M-Pesa or payment status from the payment provider."),
    ("get_business_policy", "Retrieve an approved policy."),
    ("get_current_promotions", "Retrieve current approved promotions."),
]


def business_twin_tool_schemas() -> list:
    schemas = []
    for name, description in TOOL_SPECS:
        schemas.append(
            get_function_schema(
                name,
                description,
                properties={
                    "query": {"type": "string", "description": "Customer question or identifier"},
                    "sku": {"type": "string", "description": "Product SKU when checking stock"},
                    "when": {"type": "string", "description": "ISO datetime for bookings"},
                    "order_id": {"type": "string"},
                    "reference": {"type": "string", "description": "Payment reference"},
                    "name": {"type": "string"},
                    "branch": {"type": "string"},
                },
                required=[],
            )
        )
    return schemas
