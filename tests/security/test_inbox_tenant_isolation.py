from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import Job, UserJob
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def test_inbox_cannot_be_read_or_mutated_across_tenants(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as database:
        job_a = Job(
            identity_key="a" * 64,
            title="Platform Engineer",
            company="Northstar Labs",
            location_raw="Singapore",
        )
        job_b = Job(
            identity_key="b" * 64,
            title="Data Engineer",
            company="River Systems",
            location_raw="Bangkok",
        )
        database.add_all((job_a, job_b))
        database.flush()
        item_a = UserJob(user_id=str(USER_A), job_id=job_a.id)
        item_b = UserJob(user_id=str(USER_B), job_id=job_b.id)
        database.add_all((item_a, item_b))
        database.commit()
        item_a_id = item_a.id
        item_b_id = item_b.id

    listed = client.get("/api/v1/inbox")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [item_a_id]
    assert (
        client.patch(f"/api/v1/inbox/{item_a_id}/status", json={"status": "SAVED"}).status_code
        == 200
    )
    assert (
        client.patch(f"/api/v1/inbox/{item_b_id}/status", json={"status": "SAVED"}).status_code
        == 404
    )

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="ADMIN")
    assert client.get("/api/v1/inbox").json()[0]["id"] == item_b_id
    assert (
        client.patch(f"/api/v1/inbox/{item_a_id}/status", json={"status": "SAVED"}).status_code
        == 404
    )
