async def run_agent_eval_suite(
    _ctx,
    organization_id: int,
    workflow_id: int,
    definition_id: int,
):
    """Background evaluation after a workflow is published. Never blocks the audio loop."""
    from api.services.agent_eval.service import get_agent_eval_service

    await get_agent_eval_service().run_suite(
        organization_id=organization_id,
        workflow_id=workflow_id,
        workflow_definition_id=definition_id,
        trigger="publish",
    )
