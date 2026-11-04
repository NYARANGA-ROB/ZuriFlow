"""Omnichannel customer timeline."""

from api.services.customer_timeline.service import (
    CustomerTimelineService,
    get_customer_timeline_service,
)

__all__ = ["CustomerTimelineService", "get_customer_timeline_service"]
