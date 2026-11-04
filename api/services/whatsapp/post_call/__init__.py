"""Automated post-call WhatsApp workflow."""

__all__ = ["PostCallWhatsAppOrchestrator"]


def __getattr__(name: str):
    if name == "PostCallWhatsAppOrchestrator":
        from api.services.whatsapp.post_call.orchestrator import PostCallWhatsAppOrchestrator

        return PostCallWhatsAppOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
