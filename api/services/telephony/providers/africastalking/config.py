"""Africa's Talking telephony configuration schemas."""

from typing import List, Literal

from pydantic import BaseModel, Field


class AfricasTalkingConfigurationRequest(BaseModel):
    """Request schema for Africa's Talking configuration."""

    provider: Literal["africastalking"] = Field(default="africastalking")
    username: str = Field(..., description="Africa's Talking application username")
    api_key: str = Field(..., description="Africa's Talking API key")
    from_numbers: List[str] = Field(
        default_factory=list,
        description="E.164 phone numbers registered on your AT account for outbound calls",
    )


class AfricasTalkingConfigurationResponse(BaseModel):
    """Response schema with masked sensitive fields."""

    provider: Literal["africastalking"] = Field(default="africastalking")
    username: str
    api_key: str
    from_numbers: List[str]
