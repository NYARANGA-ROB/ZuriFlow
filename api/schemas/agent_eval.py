from pydantic import BaseModel, Field


class AgentEvalStatusSchema(BaseModel):
    enabled: bool
    scenario_count: int
    categories: list[str]
    pillars: list[str]
    training_policy: str


class RunSuiteRequest(BaseModel):
    workflow_id: int | None = None
    scenario_ids: list[str] | None = None


class SampleProductionRequest(BaseModel):
    workflow_run_id: int
    consent_ok: bool = False


class TrainingGovernanceRequest(BaseModel):
    eligible: bool
    confirmation: str = Field(
        default="",
        description="Must be ALLOW_TRAINING to enable training eligibility.",
    )
