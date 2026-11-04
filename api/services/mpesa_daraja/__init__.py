"""Safaricom M-Pesa Daraja integration."""

__all__ = ["MpesaAsyncPipeline", "STKPushService"]


def __getattr__(name: str):
    if name in __all__:
        from api.services.mpesa_daraja import pipeline

        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
