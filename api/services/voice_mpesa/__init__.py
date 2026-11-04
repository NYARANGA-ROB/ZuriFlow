"""Voice-driven M-Pesa payment workflow."""

__all__ = ["VoiceMpesaWorkflowEngine"]


def __getattr__(name: str):
    if name == "VoiceMpesaWorkflowEngine":
        from api.services.voice_mpesa.engine import VoiceMpesaWorkflowEngine

        return VoiceMpesaWorkflowEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
