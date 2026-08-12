from uuid import UUID

from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import OutboxEvent
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def create_watch(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/watches",
        json={"name": "Backend roles", "target_terms": [" Python ", "python", "FastAPI"]},
    )
    assert response.status_code == 201
    return response.json()


def use_user(application: FastAPI, user_id: UUID) -> None:
    application.dependency_overrides[current_user] = lambda: CurrentUser(user_id)


def test_create_normalizes_and_lists_only_owned_watches(client: TestClient) -> None:
    created = create_watch(client)
    assert created["target_terms"] == ["Python", "FastAPI"]
    listed = client.get("/api/v1/watches").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["target_terms"] == created["target_terms"]

    use_user(app, USER_B)
    assert client.get("/api/v1/watches").json() == []
    assert client.post(f"/api/v1/watches/{created['id']}/activate").status_code == 404


def test_run_is_active_only_idempotent_and_uses_outbox(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    watch = create_watch(client)
    assert client.post(f"/api/v1/watches/{watch['id']}/runs").status_code == 409
    assert client.post(f"/api/v1/watches/{watch['id']}/activate").status_code == 200

    first = client.post(f"/api/v1/watches/{watch['id']}/runs")
    second = client.post(f"/api/v1/watches/{watch['id']}/runs")
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    with session_factory() as session:
        count = session.scalar(select(func.count()).select_from(OutboxEvent))
        event = session.scalar(select(OutboxEvent))
        assert count == 1
        assert event is not None
        assert event.event_type == "watch.discovery.requested"
        assert event.payload["owner_id"] == str(USER_A)
