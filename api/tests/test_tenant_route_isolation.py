"""Regression tests for tenant isolation on org-scoped HTTP routes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# business_call_analytics and call_reliability import enqueue_job at module load.
sys.modules.setdefault("api.tasks.arq", MagicMock(enqueue_job=MagicMock()))

from api.routes.business_call_analytics import router as business_analytics_router
from api.routes.call_reliability import router as call_reliability_router
from api.services.auth.depends import get_user_with_selected_organization
from api.services.tenant.access_control import (
    TenantIsolationViolation,
    get_tenant_context,
    scoped_organization_id,
)
from api.services.tenant.types import Permission, TenantContext, TenantRole


def _ctx(org_id: int = 11, *, superuser: bool = False) -> TenantContext:
    return TenantContext(
        organization_id=org_id,
        user_id=7,
        role=TenantRole.OWNER,
        permissions=frozenset(Permission),
        is_superuser=superuser,
        billing_enabled=False,
    )


def _make_app(ctx: TenantContext) -> FastAPI:
    app = FastAPI()
    app.include_router(business_analytics_router)
    app.include_router(call_reliability_router)
    app.dependency_overrides[get_user_with_selected_organization] = lambda: SimpleNamespace(
        id=ctx.user_id,
        selected_organization_id=ctx.organization_id,
        is_superuser=ctx.is_superuser,
    )
    app.dependency_overrides[get_tenant_context] = lambda: ctx
    return app


def test_scoped_organization_id_rejects_cross_org():
    ctx = _ctx(11)
    with pytest.raises(TenantIsolationViolation):
        scoped_organization_id(ctx, 99)


def test_scoped_organization_id_allows_own_org():
    ctx = _ctx(11)
    assert scoped_organization_id(ctx, 11) == 11


def test_business_analytics_rejects_cross_org_query():
    app = _make_app(_ctx(11))
    client = TestClient(app)

    with patch(
        "api.routes.business_call_analytics.get_business_call_analytics_service"
    ) as mock_svc:
        mock_svc.return_value.get_metrics = AsyncMock(
            return_value=SimpleNamespace(
                organization_id=99,
                from_ts=0,
                to_ts=1,
                generated_at=1,
                total_calls=0,
                kpis={},
                rates={},
            )
        )
        response = client.get(
            "/business-call-analytics/metrics",
            params={"organization_id": 99},
        )

    assert response.status_code == 403


def test_business_analytics_allows_own_org_query():
    app = _make_app(_ctx(11))
    client = TestClient(app)

    with patch(
        "api.routes.business_call_analytics.get_business_call_analytics_service"
    ) as mock_svc:
        mock_svc.return_value.get_metrics = AsyncMock(
            return_value=SimpleNamespace(
                organization_id=11,
                from_ts=0,
                to_ts=1,
                generated_at=1,
                total_calls=3,
                kpis={},
                rates={},
            )
        )
        response = client.get(
            "/business-call-analytics/metrics",
            params={"organization_id": 11},
        )

    assert response.status_code == 200
    assert response.json()["organization_id"] == 11


def test_call_reliability_scopes_failure_body_org():
    app = _make_app(_ctx(11))
    client = TestClient(app)

    with patch(
        "api.routes.call_reliability.get_call_reliability_service"
    ) as mock_svc:
        record = AsyncMock(return_value={"recorded": True})
        mock_svc.return_value.record_call_failure = record
        response = client.post(
            "/call-reliability/failures",
            json={
                "organization_id": 99,
                "reason": "test",
                "workflow_run_id": 1,
                "session_id": "s1",
                "payload": {},
                "schedule_retry": False,
            },
        )

    assert response.status_code == 403
    record.assert_not_called()


@pytest.mark.asyncio
async def test_assert_session_belongs_to_tenant_rejects_foreign_session():
    from api.services.tenant.session_tenant import assert_session_belongs_to_tenant

    ctx = _ctx(11)
    with patch(
        "api.services.tenant.session_tenant.lookup_session_organization_id",
        new=AsyncMock(return_value=99),
    ):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await assert_session_belongs_to_tenant(ctx, "foreign-session")
    assert exc.value.status_code == 404
