"""Voice campaign management package."""

from api.services.voice_campaign.service import (
    VoiceCampaignManagementService,
    get_voice_campaign_service,
)

__all__ = ["VoiceCampaignManagementService", "get_voice_campaign_service"]
