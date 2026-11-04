"""Pydantic schemas for admin operations dashboard APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AdminCapabilitiesSchema(BaseModel):
    admin_operations: bool
    realtime_calls: bool
    payment_analytics: bool
    campaign_tracking: bool
    escalation_tracking: bool
    tenant_analytics: bool
    workflow_performance: bool
    business_call_analytics: bool
    call_reliability: bool
    endpoints: Dict[str, str]


class AdminHealthSchema(BaseModel):
    enabled: bool
    status: str
    checks: Dict[str, Any]


class WorkflowRunSearchRequest(BaseModel):
    q: Optional[str] = None
    filters: Optional[List[Dict[str, Any]]] = None
    from_ts: Optional[float] = None
    to_ts: Optional[float] = None
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class CampaignSearchRequest(BaseModel):
    q: Optional[str] = None
    state: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class PaymentSearchRequest(BaseModel):
    q: Optional[str] = None
    status: Optional[str] = None
    from_ts: Optional[float] = None
    to_ts: Optional[float] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
