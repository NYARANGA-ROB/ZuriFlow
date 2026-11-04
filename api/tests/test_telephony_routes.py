from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.telephony import router
from api.schemas.organization_preferences import OrganizationPreferences
from api.services.auth.depends import get_user


def _make_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user] = lambda: SimpleNamespace(
        id=7,
        selected_organization_id=11,
    )
    return app


def _workflow(*, workflow_id: int = 33, user_id: int = 99):
    return SimpleNamespace(
        id=workflow_id,
        user_id=user_id,
        organization_id=11,
        template_context_variables={"template_key": "template-value"},
    )


def _provider():
    return SimpleNamespace(
        PROVIDER_NAME="twilio",
        WEBHOOK_ENDPOINT="twilio/voice",
        validate_config=Mock(return_value=True),
        initiate_call=AsyncMock(
            return_value=SimpleNamespace(
                caller_number="+15550001111",
                provider_metadata={"call_id": "call-123"},
            )
        ),
    )


def _failover_return(provider, *, config_id: int = 55):
    return (
        provider,
        SimpleNamespace(
            caller_number="+15550001111",
            provider_metadata={"call_id": "call-123"},
        ),
        config_id,
        [],
    )


def test_initiate_call_executes_as_workflow_owner_for_shared_org_workflow():
    app = _make_test_app()
    client = TestClient(app)

    workflow = _workflow()
    provider = _provider()
    quota_mock = AsyncMock(
        return_value=SimpleNamespace(has_quota=True, error_message="")
    )
    failover_mock = AsyncMock(return_value=_failover_return(provider))

    with (
        patch("api.routes.telephony.db_client") as mock_db,
        patch(
            "api.routes.telephony.authorize_workflow_run_start",
            new=quota_mock,
        ),
        patch(
            "api.routes.telephony.get_default_telephony_provider",
            new=AsyncMock(return_value=provider),
        ),
        patch(
            "api.services.organization_preferences.get_organization_preferences",
            new=AsyncMock(return_value=OrganizationPreferences(test_phone_number=None)),
        ),
        patch(
            "api.services.telephony.failover.initiate_call_with_failover",
            new=failover_mock,
        ),
        patch(
            "api.routes.telephony.get_backend_endpoints",
            new=AsyncMock(return_value=("https://api.example.com", "wss://ignored")),
        ),
    ):
        mock_db.get_default_telephony_configuration = AsyncMock(
            return_value=SimpleNamespace(id=55)
        )
        mock_db.get_workflow = AsyncMock(return_value=workflow)
        mock_db.create_workflow_run = AsyncMock(
            return_value=SimpleNamespace(
                id=501,
                name="WR-TEL-OUT-00000001",
                initial_context={"template_key": "template-value"},
            )
        )
        mock_db.update_workflow_run = AsyncMock()

        response = client.post(
            "/telephony/initiate-call",
            json={"workflow_id": workflow.id, "phone_number": "+15551234567"},
        )

    assert response.status_code == 200
    quota_mock.assert_awaited_once_with(
        workflow_id=workflow.id,
        workflow_run_id=501,
        actor_user=ANY,
    )
    mock_db.get_workflow.assert_awaited_once_with(workflow.id, organization_id=11)

    create_call = mock_db.create_workflow_run.await_args
    create_args = create_call.args
    create_kwargs = create_call.kwargs
    assert create_args[1] == workflow.id
    assert create_kwargs["user_id"] == workflow.user_id
    assert create_kwargs["organization_id"] == workflow.organization_id
    assert create_kwargs["initial_context"]["template_key"] == "template-value"

    failover_kwargs = failover_mock.await_args.kwargs
    assert failover_kwargs["initiate_kwargs"]["user_id"] == workflow.user_id
    assert failover_kwargs["initiate_kwargs"]["workflow_id"] == workflow.id
    assert failover_kwargs["to_number"] == "+15551234567"


def test_initiate_call_uses_organization_preference_phone_number():
    app = _make_test_app()
    client = TestClient(app)

    workflow = _workflow()
    provider = _provider()
    quota_mock = AsyncMock(
        return_value=SimpleNamespace(has_quota=True, error_message="")
    )
    failover_mock = AsyncMock(return_value=_failover_return(provider))

    with (
        patch("api.routes.telephony.db_client") as mock_db,
        patch(
            "api.routes.telephony.authorize_workflow_run_start",
            new=quota_mock,
        ),
        patch(
            "api.routes.telephony.get_default_telephony_provider",
            new=AsyncMock(return_value=provider),
        ),
        patch(
            "api.services.organization_preferences.get_organization_preferences",
            new=AsyncMock(
                return_value=OrganizationPreferences(test_phone_number="+15557654321")
            ),
        ),
        patch(
            "api.services.telephony.failover.initiate_call_with_failover",
            new=failover_mock,
        ),
        patch(
            "api.routes.telephony.get_backend_endpoints",
            new=AsyncMock(return_value=("https://api.example.com", "wss://ignored")),
        ),
    ):
        mock_db.get_default_telephony_configuration = AsyncMock(
            return_value=SimpleNamespace(id=55)
        )
        mock_db.get_workflow = AsyncMock(return_value=workflow)
        mock_db.create_workflow_run = AsyncMock(
            return_value=SimpleNamespace(
                id=501,
                name="WR-TEL-OUT-00000001",
                initial_context={},
            )
        )
        mock_db.update_workflow_run = AsyncMock()

        response = client.post(
            "/telephony/initiate-call",
            json={"workflow_id": workflow.id},
        )

    assert response.status_code == 200
    assert failover_mock.await_args.kwargs["to_number"] == "+15557654321"


def test_initiate_call_rejects_existing_run_for_different_workflow():
    app = _make_test_app()
    client = TestClient(app)

    workflow = _workflow()
    provider = _provider()
    quota_mock = AsyncMock(
        return_value=SimpleNamespace(has_quota=True, error_message="")
    )

    with (
        patch("api.routes.telephony.db_client") as mock_db,
        patch(
            "api.routes.telephony.authorize_workflow_run_start",
            new=quota_mock,
        ),
        patch(
            "api.routes.telephony.get_default_telephony_provider",
            new=AsyncMock(return_value=provider),
        ),
        patch(
            "api.services.organization_preferences.get_organization_preferences",
            new=AsyncMock(return_value=OrganizationPreferences(test_phone_number=None)),
        ),
    ):
        mock_db.get_default_telephony_configuration = AsyncMock(
            return_value=SimpleNamespace(id=55)
        )
        mock_db.get_workflow = AsyncMock(return_value=workflow)
        mock_db.get_workflow_run = AsyncMock(
            return_value=SimpleNamespace(
                id=501,
                workflow_id=44,
                name="WR-TEL-OUT-00000044",
                initial_context={},
            )
        )

        response = client.post(
            "/telephony/initiate-call",
            json={
                "workflow_id": workflow.id,
                "workflow_run_id": 501,
                "phone_number": "+15551234567",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "workflow_run_workflow_mismatch"
    mock_db.get_workflow_run.assert_awaited_once_with(501, organization_id=11)
    assert not mock_db.create_workflow_run.called
    assert provider.initiate_call.await_count == 0
