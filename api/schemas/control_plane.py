from typing import Any, Literal

from pydantic import BaseModel, Field

from api.services.control_plane.setup import OrganizationSetupProfile

__all__ = ["OrganizationSetupProfile"]


class BusinessKnowledgeCreate(BaseModel):
    category: str
    title: str
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_uuid: str | None = None


class BusinessKnowledgeUpdate(BaseModel):
    category: str | None = None
    title: str | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None
    document_uuid: str | None = None
    is_active: bool | None = None


class BusinessToolInstallRequest(BaseModel):
    key: str
    endpoint_url: str | None = None
    transfer_destination: str | None = None


class WorkflowEnvironmentPromoteRequest(BaseModel):
    target: Literal["testing", "staging", "published"]
    changelog: str | None = None


class WorkflowRollbackRequest(BaseModel):
    definition_id: int
    changelog: str | None = None
