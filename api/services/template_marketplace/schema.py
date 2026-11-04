"""Marketplace catalog schema — listings, versions, and tenant customization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from api.services.vertical_workflows.schema import VerticalWorkflowTemplate


class TemplateVersionStatus(str, Enum):
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    DRAFT = "draft"


@dataclass(frozen=True)
class TemplateVersionInfo:
    version: str
    released_at: str
    changelog: str
    status: TemplateVersionStatus = TemplateVersionStatus.PUBLISHED

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "released_at": self.released_at,
            "changelog": self.changelog,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class MarketplaceTemplateListing:
    """Searchable marketplace entry wrapping a versioned vertical template."""

    template_id: str
    template: VerticalWorkflowTemplate
    tags: tuple[str, ...] = ()
    search_keywords: tuple[str, ...] = ()
    category: str = "general"
    featured: bool = False
    icon: str = "workflow"
    version_history: tuple[TemplateVersionInfo, ...] = ()

    @property
    def latest_version(self) -> str:
        return self.template.version

    def to_summary_dict(self) -> dict[str, Any]:
        t = self.template
        return {
            "template_id": self.template_id,
            "name": t.name,
            "industry": t.industry.value,
            "version": t.version,
            "description": t.description,
            "default_locale": t.default_locale,
            "supported_locales": list(t.supported_locales),
            "integrations": t.integrations.to_dict(),
            "tags": list(self.tags),
            "category": self.category,
            "featured": self.featured,
            "icon": self.icon,
            "extends_template_id": t.extends_template_id,
            "latest_version": self.latest_version,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        data = self.to_summary_dict()
        data["template"] = self.template.to_dict()
        data["version_history"] = [v.to_dict() for v in self.version_history]
        data["search_keywords"] = list(self.search_keywords)
        return data


@dataclass
class TenantTemplateCustomization:
    """Per-organization overrides for a marketplace template."""

    template_id: str
    pinned_version: str | None = None
    default_locale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    global_rules: list[dict[str, Any]] = field(default_factory=list)
    steps: dict[str, dict[str, Any]] = field(default_factory=dict)
    prompt_overrides: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pinned_version": self.pinned_version,
            "default_locale": self.default_locale,
            "metadata": dict(self.metadata),
            "global_rules": list(self.global_rules),
            "steps": dict(self.steps),
            "prompt_overrides": dict(self.prompt_overrides),
        }

    @classmethod
    def from_dict(cls, template_id: str, raw: dict[str, Any] | None) -> TenantTemplateCustomization:
        raw = raw or {}
        return cls(
            template_id=template_id,
            pinned_version=raw.get("pinned_version"),
            default_locale=raw.get("default_locale"),
            metadata=dict(raw.get("metadata") or {}),
            global_rules=list(raw.get("global_rules") or []),
            steps=dict(raw.get("steps") or {}),
            prompt_overrides=dict(raw.get("prompt_overrides") or {}),
        )


@dataclass(frozen=True)
class TemplateSearchQuery:
    q: str = ""
    industry: str | None = None
    tag: str | None = None
    category: str | None = None
    locale: str | None = None
    featured_only: bool = False
    limit: int = 50
