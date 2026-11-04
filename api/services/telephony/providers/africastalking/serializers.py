"""Frame serializer for Africa's Talking media streams.

Africa's Talking bidirectional streams use the same Plivo-compatible WebSocket
framing when exposed via SIP or partner gateways. Re-use the Plivo serializer.
"""

from pipecat.serializers.plivo import PlivoFrameSerializer

__all__ = ["PlivoFrameSerializer"]
