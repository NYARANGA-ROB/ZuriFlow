"""HTTP route tests for organization telephony failover configuration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.organization import router
from api.services.auth.depends import get_user


def _make_test_app(*, organization_id: int | None = 11) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user] = lambda: SimpleNamespace(
        id=7,
        selected_organization_id=organization_id,
    )
    return app


def test_get_telephony_failover_returns_configuration():
    app = _make_test_app()
    client = TestClient(app)

    with patch(
        "api.services.telephony.failover.get_failover_configuration",
        new=AsyncMock(return_value={"enabled": True, "configuration_ids": [2, 5]}),
    ) as get_mock:
        response = client.get("/organizations/telephony-failover")

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "configuration_ids": [2, 5]}
    get_mock.assert_awaited_once_with(11)


def test_get_telephony_failover_requires_selected_organization():
    app = _make_test_app(organization_id=None)
    client = TestClient(app)

    response = client.get("/organizations/telephony-failover")

    assert response.status_code == 400
    assert response.json()["detail"] == "No organization selected"


def test_put_telephony_failover_persists_valid_configuration():
    app = _make_test_app()
    client = TestClient(app)

    with (
        patch("api.routes.organization.db_client") as mock_db,
        patch(
            "api.services.telephony.failover.save_failover_configuration",
            new=AsyncMock(
                return_value={"enabled": True, "configuration_ids": [3, 1]}
            ),
        ) as save_mock,
    ):
        mock_db.get_telephony_configuration_for_org = AsyncMock(
            return_value=SimpleNamespace(id=3)
        )

        response = client.put(
            "/organizations/telephony-failover",
            json={"enabled": True, "configuration_ids": [3, 1]},
        )

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "configuration_ids": [3, 1]}
    assert mock_db.get_telephony_configuration_for_org.await_count == 2
    save_mock.assert_awaited_once_with(11, enabled=True, configuration_ids=[3, 1])


def test_put_telephony_failover_rejects_unknown_configuration():
    app = _make_test_app()
    client = TestClient(app)

    with patch("api.routes.organization.db_client") as mock_db:
        mock_db.get_telephony_configuration_for_org = AsyncMock(
            side_effect=[SimpleNamespace(id=3), None]
        )

        response = client.put(
            "/organizations/telephony-failover",
            json={"enabled": True, "configuration_ids": [3, 99]},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "telephony_configuration_not_found:99"
