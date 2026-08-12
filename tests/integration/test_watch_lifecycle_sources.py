from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import JobWatch, WatchSource
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def test_watch_sources_are_owned_and_lifecycle_is_explicit(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    payload = {
        "name": "Public platform roles",
        "target_terms": ["Python"],
        "work_arrangements": ["REMOTE"],
        "employment_types": ["FULL_TIME"],
        "sources": [
            {"source_kind": "PLATFORM", "adapter_key": "synthetic_board"},
            {
                "source_kind": "CUSTOM_URL",
                "adapter_key": "generic_public",
                "url": "https://careers.example.invalid/jobs#openings",
            },
        ],
    }
    created = client.post("/api/v1/watches", json=payload)
    assert created.status_code == 201
    watch_id = created.json()["id"]
    assert created.json()["sources"][1]["url"] == "https://careers.example.invalid/jobs"
    assert client.post(f"/api/v1/watches/{watch_id}/activate").status_code == 200
    assert client.post(f"/api/v1/watches/{watch_id}/pause").json()["status"] == "PAUSED"
    assert client.post(f"/api/v1/watches/{watch_id}/archive").json()["status"] == "ARCHIVED"
    assert client.put(f"/api/v1/watches/{watch_id}", json=payload).status_code == 409

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B)
    assert client.get(f"/api/v1/watches/{watch_id}").status_code == 404
    assert client.delete(f"/api/v1/watches/{watch_id}").status_code == 404

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A)
    assert client.delete(f"/api/v1/watches/{watch_id}").status_code == 204
    with session_factory() as database:
        assert database.scalar(select(func.count()).select_from(JobWatch)) == 0
        assert database.scalar(select(func.count()).select_from(WatchSource)) == 0


def test_custom_source_rejects_private_or_credentialed_urls(client: TestClient) -> None:
    for unsafe_url in (
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "https://user:password@example.com/jobs",
        "https://example.com:8443/jobs",
    ):
        response = client.post(
            "/api/v1/watches",
            json={
                "name": "Unsafe source",
                "target_terms": ["Engineer"],
                "sources": [
                    {
                        "source_kind": "CUSTOM_URL",
                        "adapter_key": "generic_public",
                        "url": unsafe_url,
                    }
                ],
            },
        )
        assert response.status_code == 422
