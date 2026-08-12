from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import AuditEvent, PlatformControl, User
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def test_superadmin_kill_switch_is_audited_and_blocks_manual_work(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as database:
        database.add_all(
            [
                User(
                    id=str(USER_A),
                    cognito_subject="control-user",
                    email="control-user@example.invalid",
                ),
                User(
                    id=str(USER_B),
                    cognito_subject="control-admin",
                    email="control-admin@example.invalid",
                    role="SUPERADMIN",
                    mfa_enabled=True,
                ),
            ]
        )
        database.commit()

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    response = client.put("/api/v1/admin/operations/controls/MANUAL_RUN", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A)
    watch = client.post(
        "/api/v1/watches", json={"name": "Controlled", "target_terms": ["Python"]}
    ).json()
    assert client.post(f"/api/v1/watches/{watch['id']}/activate").status_code == 200
    blocked = client.post(f"/api/v1/watches/{watch['id']}/runs")
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "MANUAL_RUN_DISABLED"

    with session_factory() as database:
        assert database.get(PlatformControl, "MANUAL_RUN") is not None
        audit = database.scalar(
            select(AuditEvent).where(AuditEvent.action == "PLATFORM_CONTROL_UPDATED")
        )
        assert audit is not None
        assert audit.change_metadata["after"] == {"enabled": False}
