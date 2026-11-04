"""Built-in send_dtmf tool schema for telephony IVR navigation."""

from typing import Any, Dict, List


def get_send_dtmf_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "send_dtmf",
                "description": (
                    "Send DTMF keypad tones on the active phone call. Use when navigating "
                    "an IVR phone menu."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "digits": {
                            "type": "string",
                            "description": (
                                "DTMF digits to send (0-9, *, #). Example: '1' or '12#'."
                            ),
                        }
                    },
                    "required": ["digits"],
                },
            },
        }
    ]
