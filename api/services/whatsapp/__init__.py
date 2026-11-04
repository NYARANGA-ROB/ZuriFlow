"""WhatsApp integration for AI voice agents."""

__all__ = ["WhatsAppMessagingService"]


def __getattr__(name: str):
    if name == "WhatsAppMessagingService":
        from api.services.whatsapp.messaging import WhatsAppMessagingService

        return WhatsAppMessagingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
