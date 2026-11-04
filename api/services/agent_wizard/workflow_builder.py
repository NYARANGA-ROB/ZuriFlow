"""Build starter workflow graphs from vertical templates."""

from __future__ import annotations

import uuid

from api.services.agent_wizard.schema import AgentWizardConfig, PersonalityConfig
from api.services.vertical_workflows.registry import get_vertical_workflow_registry
from api.services.vertical_workflows.schema import VerticalWorkflowTemplate, WorkflowStepKind
from api.services.workflow.trigger_paths import regenerate_trigger_uuids

_KIND_NODE_NAME = {
    WorkflowStepKind.GREETING: "Greeting",
    WorkflowStepKind.LANGUAGE_SELECT: "Language",
    WorkflowStepKind.IDENTIFY: "Identify customer",
    WorkflowStepKind.QUALIFY: "Understand request",
    WorkflowStepKind.FAQ: "Common questions",
    WorkflowStepKind.COLLECT: "Collect details",
    WorkflowStepKind.COLLECT_PAYMENT: "Payments",
    WorkflowStepKind.SUPPORT: "Help",
    WorkflowStepKind.ESCALATION: "Talk to a person",
    WorkflowStepKind.SUMMARY: "Call summary",
    WorkflowStepKind.CLOSING: "End call",
    WorkflowStepKind.BOOKING: "Booking",
}


def _step_prompt(template: VerticalWorkflowTemplate, step_kind: WorkflowStepKind, locale: str) -> str:
    for step in template.steps:
        if step.kind == step_kind:
            prompts = step.prompts.system
            if locale in prompts:
                return prompts[locale]
            if "mixed" in prompts:
                return prompts["mixed"]
            if prompts:
                return next(iter(prompts.values()))
    return ""


def _prompt_for_step(template: VerticalWorkflowTemplate, step, locale: str) -> str:
    prompts = step.prompts.system
    if locale in prompts:
        return prompts[locale]
    if template.default_locale in prompts:
        return prompts[template.default_locale]
    if prompts:
        return next(iter(prompts.values()))
    return "Help the caller clearly and politely."


def build_workflow_definition(config: AgentWizardConfig) -> dict:
    """Create a publish-ready workflow graph snapshot from the pinned template."""
    assert config.industry is not None and config.workflow is not None

    template_id = config.industry.template_id or "kenya_mp_contact_center"
    registry = get_vertical_workflow_registry()
    template = registry.require(template_id)
    locale = config.locale.primary_locale if config.locale else template.default_locale
    wf = config.workflow
    personality = config.personality or PersonalityConfig()
    style_line = f" Speak in a {personality.style.replace('_', ' ')} Kenyan customer-care style."

    node_ids: list[str] = []
    nodes: list[dict] = []
    steps = list(template.steps) or []
    if not steps:
        greeting = _step_prompt(template, WorkflowStepKind.GREETING, locale) or (
            "You are a helpful voice agent for a Kenyan business."
        )
        steps = []  # fall through to minimal below

    if template.steps:
        for index, step in enumerate(template.steps):
            nid = str(uuid.uuid4())
            node_ids.append(nid)
            is_first = index == 0
            is_last = index == len(template.steps) - 1
            if is_first:
                ntype = "startCall"
            elif is_last or step.kind in {WorkflowStepKind.CLOSING}:
                ntype = "endCall"
            else:
                ntype = "agentNode"
            prompt = _prompt_for_step(template, step, locale) + style_line
            data: dict = {
                "name": _KIND_NODE_NAME.get(step.kind, step.name),
                "prompt": prompt,
                "allow_interrupt": True,
                "template_step_id": step.step_id,
            }
            if ntype == "startCall":
                data["greeting"] = f"Hello, welcome to {wf.agent_name}."
                data["greeting_type"] = "text"
            nodes.append(
                {
                    "id": nid,
                    "type": ntype,
                    "position": {"x": index * 240, "y": 0},
                    "data": data,
                }
            )
    else:
        start_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        end_id = str(uuid.uuid4())
        node_ids = [start_id, agent_id, end_id]
        greeting = _step_prompt(template, WorkflowStepKind.GREETING, locale)
        support = _step_prompt(template, WorkflowStepKind.SUPPORT, locale)
        nodes = [
            {
                "id": start_id,
                "type": "startCall",
                "position": {"x": 0, "y": 0},
                "data": {
                    "name": "Greeting",
                    "prompt": greeting + style_line,
                    "greeting": f"Hello, welcome to {wf.agent_name}.",
                    "greeting_type": "text",
                    "allow_interrupt": True,
                },
            },
            {
                "id": agent_id,
                "type": "agentNode",
                "position": {"x": 280, "y": 0},
                "data": {"name": "Support", "prompt": support + style_line, "allow_interrupt": True},
            },
            {
                "id": end_id,
                "type": "endCall",
                "position": {"x": 560, "y": 0},
                "data": {"name": "End Call", "prompt": "Thank the caller and end politely."},
            },
        ]

    edges = [
        {
            "id": str(uuid.uuid4()),
            "source": node_ids[i],
            "target": node_ids[i + 1],
            "label": "continue",
        }
        for i in range(len(node_ids) - 1)
    ]

    if wf.call_direction == "outbound":
        trigger_id = str(uuid.uuid4())
        nodes.insert(
            0,
            {
                "id": trigger_id,
                "type": "trigger",
                "position": {"x": -280, "y": 0},
                "data": {"name": "Start call", "enabled": True},
            },
        )
        if node_ids:
            edges.insert(
                0,
                {
                    "id": str(uuid.uuid4()),
                    "source": trigger_id,
                    "target": node_ids[0],
                    "label": "start",
                },
            )

    definition = {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}
    return regenerate_trigger_uuids(definition) or definition


def build_workflow_configurations(config: AgentWizardConfig) -> dict:
    """Attach wizard metadata, pinning the template version on this agent."""
    registry = get_vertical_workflow_registry()
    template_id = config.industry.template_id if config.industry else None
    template = registry.get(template_id) if template_id else None
    pinned = template.version if template else None
    meta: dict = {
        "agent_wizard": {
            "industry_id": config.industry.industry_id if config.industry else None,
            "template_id": template_id,
            "template_version": pinned,
            "locale": config.locale.model_dump() if config.locale else None,
            "payments": config.payments.model_dump() if config.payments else None,
            "crm": config.crm.model_dump() if config.crm else None,
            "escalation": config.escalation.model_dump() if config.escalation else None,
            "personality": config.personality.model_dump() if config.personality else None,
            "business_hours": config.business_hours.model_dump() if config.business_hours else None,
        }
    }
    if config.voice:
        meta["model_overrides"] = {
            "tts": {
                "provider": config.voice.provider,
                "voice": config.voice.voice_id,
                "speed": config.voice.speed,
                "language": config.voice.language,
            }
        }
    return meta
