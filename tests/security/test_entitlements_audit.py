from uuid import uuid4

import pytest
from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import AccountActivity, AuditEvent, PlanEntitlement
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def test_plan_limit_blocks_additional_active_watch(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as database:
        database.add(
            PlanEntitlement(
                plan="FREE", entitlement_key="active_watch_count", enabled=True, limit_value=1
            )
        )
        database.commit()

    first = create_watch(client, "First")
    second = create_watch(client, "Second")
    assert client.post(f"/api/v1/watches/{first}/activate").status_code == 200
    blocked = client.post(f"/api/v1/watches/{second}/activate")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_account_activity_is_tenant_scoped(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as database:
        database.add_all(
            (
                AccountActivity(user_id=str(USER_A), activity_type="SIGNED_IN"),
                AccountActivity(user_id=str(USER_B), activity_type="PASSWORD_CHANGED"),
            )
        )
        database.commit()
    response = client.get("/api/v1/account/activity")
    assert response.status_code == 200
    assert [item["activity_type"] for item in response.json()] == ["SIGNED_IN"]


def test_audit_events_cannot_be_updated_or_deleted(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as database:
        event = AuditEvent(
            actor_user_id=str(USER_A),
            actor_role="SUPERADMIN",
            action="TEST_ACTION",
            target_type="TEST",
            target_id=None,
            result="SUCCEEDED",
            correlation_id=str(uuid4()),
        )
        database.add(event)
        database.commit()
        event.result = "ALTERED"
        with pytest.raises(ValueError, match="append-only"):
            database.commit()


def test_only_superadmin_can_change_entitlements_and_change_is_audited(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    payload = {"enabled": True, "limit_value": 4}
    denied = client.put("/api/v1/admin/entitlements/plans/FREE/active_watch_count", json=payload)
    assert denied.status_code == 403

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A, role="SUPERADMIN")
    changed = client.put("/api/v1/admin/entitlements/plans/FREE/active_watch_count", json=payload)
    assert changed.status_code == 200
    assert changed.json()["limit_value"] == 4
    with session_factory() as database:
        audit = database.scalar(select(AuditEvent))
        assert audit is not None
        assert audit.action == "ENTITLEMENT_UPDATED"
        assert audit.change_metadata["after"]["limit_value"] == 4


def create_watch(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/watches", json={"name": name, "target_terms": ["Platform Engineer"]}
    )
    assert response.status_code == 201
    return response.json()["id"]
