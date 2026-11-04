"""Vertical workflow schema — templates, rules, steps, and runtime instances."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VerticalIndustry(str, Enum):
    FINTECH_KENYA = "fintech_kenya"
    DEBT_COLLECTION = "debt_collection"
    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    HOSPITALITY = "hospitality"
    GENERAL = "general"
    LOGISTICS = "logistics"
    SACCO = "sacco"
    EDUCATION = "education"
    MICROFINANCE = "microfinance"
    BANKING = "banking"
    INSURANCE = "insurance"
    HOSPITALS = "hospitals"
    PHARMACIES = "pharmacies"
    SCHOOLS = "schools"
    UNIVERSITIES = "universities"
    REAL_ESTATE = "real_estate"
    PROPERTY_MANAGEMENT = "property_management"
    HOTELS = "hotels"
    RESTAURANTS = "restaurants"
    ECOMMERCE = "ecommerce"
    COURIER = "courier"
    MATATU = "matatu"
    CAR_DEALERSHIPS = "car_dealerships"
    GARAGES = "garages"
    TRAVEL = "travel"
    AGRICULTURE = "agriculture"
    NGO = "ngo"
    GOVERNMENT = "government"
    UTILITIES = "utilities"
    SECURITY = "security"
    CONTACT_CENTER = "contact_center"


class WorkflowStepKind(str, Enum):
    GREETING = "greeting"
    QUALIFY = "qualify"
    NEGOTIATION = "negotiation"
    INSTALLMENT = "installment"
    COLLECT_PAYMENT = "collect_payment"
    BOOKING = "booking"
    SUPPORT = "support"
    ESCALATION = "escalation"
    CLOSING = "closing"
    LANGUAGE_SELECT = "language_select"
    IDENTIFY = "identify"
    FAQ = "faq"
    COLLECT = "collect"
    SUMMARY = "summary"


class RuleOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    IN = "in"
    INTENT_IS = "intent_is"
    LANGUAGE_IN = "language_in"
    ALWAYS = "always"


class RuleActionType(str, Enum):
    ADVANCE_STEP = "advance_step"
    SET_VARIABLE = "set_variable"
    ESCALATE = "escalate"
    REQUEST_PAYMENT = "request_payment"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_SMS = "send_sms"
    START_CALL = "start_call"
    WAIT_FOR_REPLY = "wait_for_reply"
    SEND_RECEIPT = "send_receipt"
    SEND_DOCUMENT = "send_document"
    ROUTE_QUEUE = "route_queue"
    END_WORKFLOW = "end_workflow"


class WorkflowInstanceStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_PAYMENT = "waiting_payment"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowEventType(str, Enum):
    START = "start"
    TRANSCRIPT = "transcript"
    INTENT = "intent"
    PAYMENT_STATUS = "payment_status"
    ESCALATION = "escalation"
    MANUAL = "manual"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class MultilingualPrompt:
    """Locale-keyed prompt fragments for a workflow step."""

    default_locale: str = "en"
    system: dict[str, str] = field(default_factory=dict)
    user_hint: dict[str, str] = field(default_factory=dict)

    def resolve(self, locale: str | None = None, *, kind: str = "system") -> str:
        loc = locale or self.default_locale
        bucket = self.system if kind == "system" else self.user_hint
        if loc in bucket:
            return bucket[loc]
        if self.default_locale in bucket:
            return bucket[self.default_locale]
        return next(iter(bucket.values()), "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_locale": self.default_locale,
            "system": dict(self.system),
            "user_hint": dict(self.user_hint),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> MultilingualPrompt:
        raw = raw or {}
        return cls(
            default_locale=str(raw.get("default_locale", "en")),
            system=dict(raw.get("system") or {}),
            user_hint=dict(raw.get("user_hint") or {}),
        )


@dataclass(frozen=True)
class IntegrationBindings:
    """Which external integrations a vertical template may invoke."""

    mpesa: bool = False
    whatsapp: bool = False
    call_routing: bool = False
    kenyan_intent: bool = True
    sms: bool = False
    kenya_hours: bool = True
    kenya_holidays: bool = True
    kes: bool = True
    phone_ke: bool = True
    crm_timeline: bool = True
    analytics: bool = True
    sheng: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "mpesa": self.mpesa,
            "whatsapp": self.whatsapp,
            "call_routing": self.call_routing,
            "kenyan_intent": self.kenyan_intent,
            "sms": self.sms,
            "kenya_hours": self.kenya_hours,
            "kenya_holidays": self.kenya_holidays,
            "kes": self.kes,
            "phone_ke": self.phone_ke,
            "crm_timeline": self.crm_timeline,
            "analytics": self.analytics,
            "sheng": self.sheng,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> IntegrationBindings:
        raw = raw or {}
        return cls(
            mpesa=bool(raw.get("mpesa", False)),
            whatsapp=bool(raw.get("whatsapp", False)),
            call_routing=bool(raw.get("call_routing", False)),
            kenyan_intent=bool(raw.get("kenyan_intent", True)),
            sms=bool(raw.get("sms", False)),
            kenya_hours=bool(raw.get("kenya_hours", True)),
            kenya_holidays=bool(raw.get("kenya_holidays", True)),
            kes=bool(raw.get("kes", True)),
            phone_ke=bool(raw.get("phone_ke", True)),
            crm_timeline=bool(raw.get("crm_timeline", True)),
            analytics=bool(raw.get("analytics", True)),
            sheng=bool(raw.get("sheng", True)),
        )


@dataclass(frozen=True)
class RuleCondition:
    field: str
    operator: RuleOperator
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuleCondition:
        return cls(
            field=str(raw["field"]),
            operator=RuleOperator(raw.get("operator", RuleOperator.ALWAYS.value)),
            value=raw.get("value"),
        )


@dataclass(frozen=True)
class RuleAction:
    action: RuleActionType
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action.value, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuleAction:
        return cls(
            action=RuleActionType(raw["action"]),
            params=dict(raw.get("params") or {}),
        )


@dataclass(frozen=True)
class BusinessRule:
    """Declarative when/then rule evaluated against workflow context."""

    rule_id: str
    name: str
    when: RuleCondition
    then: tuple[RuleAction, ...] = ()
    priority: int = 100
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "when": self.when.to_dict(),
            "then": [a.to_dict() for a in self.then],
            "priority": self.priority,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BusinessRule:
        return cls(
            rule_id=str(raw["rule_id"]),
            name=str(raw.get("name", raw["rule_id"])),
            when=RuleCondition.from_dict(raw["when"]),
            then=tuple(RuleAction.from_dict(a) for a in raw.get("then") or []),
            priority=int(raw.get("priority", 100)),
            enabled=bool(raw.get("enabled", True)),
        )


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    name: str
    kind: WorkflowStepKind
    prompts: MultilingualPrompt = field(default_factory=MultilingualPrompt)
    next_step_id: str | None = None
    rules: tuple[BusinessRule, ...] = ()
    timeout_s: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "kind": self.kind.value,
            "prompts": self.prompts.to_dict(),
            "next_step_id": self.next_step_id,
            "rules": [r.to_dict() for r in self.rules],
            "timeout_s": self.timeout_s,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowStep:
        return cls(
            step_id=str(raw["step_id"]),
            name=str(raw.get("name", raw["step_id"])),
            kind=WorkflowStepKind(raw.get("kind", WorkflowStepKind.SUPPORT.value)),
            prompts=MultilingualPrompt.from_dict(raw.get("prompts")),
            next_step_id=raw.get("next_step_id"),
            rules=tuple(BusinessRule.from_dict(r) for r in raw.get("rules") or []),
            timeout_s=raw.get("timeout_s"),
        )


@dataclass(frozen=True)
class VerticalWorkflowTemplate:
    """Reusable vertical blueprint: steps, prompts, rules, integrations."""

    template_id: str
    name: str
    industry: VerticalIndustry
    version: str = "1.0.0"
    description: str = ""
    default_locale: str = "en"
    supported_locales: tuple[str, ...] = ("en", "sw")
    entry_step_id: str = "greeting"
    steps: tuple[WorkflowStep, ...] = ()
    global_rules: tuple[BusinessRule, ...] = ()
    integrations: IntegrationBindings = field(default_factory=IntegrationBindings)
    metadata: dict[str, Any] = field(default_factory=dict)
    extends_template_id: str | None = None
    extends_version: str | None = None

    def step(self, step_id: str) -> WorkflowStep | None:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def entry_step(self) -> WorkflowStep | None:
        return self.step(self.entry_step_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "industry": self.industry.value,
            "version": self.version,
            "description": self.description,
            "default_locale": self.default_locale,
            "supported_locales": list(self.supported_locales),
            "entry_step_id": self.entry_step_id,
            "steps": [s.to_dict() for s in self.steps],
            "global_rules": [r.to_dict() for r in self.global_rules],
            "integrations": self.integrations.to_dict(),
            "metadata": dict(self.metadata),
            "extends_template_id": self.extends_template_id,
            "extends_version": self.extends_version,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> VerticalWorkflowTemplate:
        return cls(
            template_id=str(raw["template_id"]),
            name=str(raw["name"]),
            industry=VerticalIndustry(raw["industry"]),
            version=str(raw.get("version", "1.0.0")),
            description=str(raw.get("description", "")),
            default_locale=str(raw.get("default_locale", "en")),
            supported_locales=tuple(raw.get("supported_locales") or ("en", "sw")),
            entry_step_id=str(raw.get("entry_step_id", "greeting")),
            steps=tuple(WorkflowStep.from_dict(s) for s in raw.get("steps") or []),
            global_rules=tuple(
                BusinessRule.from_dict(r) for r in raw.get("global_rules") or []
            ),
            integrations=IntegrationBindings.from_dict(raw.get("integrations")),
            metadata=dict(raw.get("metadata") or {}),
            extends_template_id=raw.get("extends_template_id"),
            extends_version=raw.get("extends_version"),
        )


@dataclass
class WorkflowEvent:
    event_type: WorkflowEventType
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecutionResult:
    instance_id: str
    status: WorkflowInstanceStatus
    current_step_id: str
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    escalated: bool = False
    payment_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "status": self.status.value,
            "current_step_id": self.current_step_id,
            "actions_taken": list(self.actions_taken),
            "variables": dict(self.variables),
            "prompt": self.prompt,
            "escalated": self.escalated,
            "payment_requested": self.payment_requested,
        }


@dataclass
class VerticalWorkflowInstance:
    """Runtime state for one vertical workflow execution."""

    instance_id: str
    template_id: str
    organization_id: int
    workflow_run_id: int | None = None
    status: WorkflowInstanceStatus = WorkflowInstanceStatus.PENDING
    current_step_id: str = ""
    locale: str = "en"
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "template_id": self.template_id,
            "organization_id": self.organization_id,
            "workflow_run_id": self.workflow_run_id,
            "status": self.status.value,
            "current_step_id": self.current_step_id,
            "locale": self.locale,
            "variables": dict(self.variables),
            "history": list(self.history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> VerticalWorkflowInstance:
        return cls(
            instance_id=str(raw["instance_id"]),
            template_id=str(raw["template_id"]),
            organization_id=int(raw["organization_id"]),
            workflow_run_id=raw.get("workflow_run_id"),
            status=WorkflowInstanceStatus(raw.get("status", WorkflowInstanceStatus.PENDING.value)),
            current_step_id=str(raw.get("current_step_id", "")),
            locale=str(raw.get("locale", "en")),
            variables=dict(raw.get("variables") or {}),
            history=list(raw.get("history") or []),
            created_at=float(raw.get("created_at", 0.0)),
            updated_at=float(raw.get("updated_at", 0.0)),
        )
