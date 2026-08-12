from datetime import UTC, datetime, timedelta

from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import Job, UserJob
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def seed_owned_job(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as database:
        job = Job(
            identity_key="c" * 64,
            title="Platform Engineer",
            company="Synthetic Systems",
            location_raw="Remote, Thailand",
        )
        database.add(job)
        database.flush()
        database.add(UserJob(user_id=str(USER_A), job_id=job.id))
        database.commit()
        return job.id


def test_application_notes_interviews_and_reminders_are_owner_controlled(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    job_id = seed_owned_job(session_factory)
    created = client.post("/api/v1/applications", json={"job_id": job_id, "status": "APPLIED"})
    assert created.status_code == 201
    application_id = created.json()["id"]
    assert created.json()["applied_at"] == datetime.now(UTC).date().isoformat()

    note = client.post(
        f"/api/v1/applications/{application_id}/notes",
        json={"note_type": "RECRUITER_CALL", "body": "Synthetic private note"},
    )
    assert note.status_code == 201
    interview = client.post(
        f"/api/v1/applications/{application_id}/interviews",
        json={"stage": "TECHNICAL", "went_well": "Clear system design explanation"},
    )
    assert interview.status_code == 201
    reminder = client.post(
        f"/api/v1/applications/{application_id}/reminders",
        json={
            "reminder_type": "INTERVIEW",
            "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert reminder.status_code == 201
    assert client.get(f"/api/v1/applications/{application_id}/notes").status_code == 200
    assert client.get(f"/api/v1/applications/{application_id}/interviews").status_code == 200
    assert client.get(f"/api/v1/applications/{application_id}/reminders").status_code == 200
    assert client.get(f"/api/v1/applications/{application_id}").json()["status"] == "APPLIED"


def test_other_user_and_admin_cannot_enumerate_read_update_or_delete_application(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    job_id = seed_owned_job(session_factory)
    created = client.post("/api/v1/applications", json={"job_id": job_id})
    application_id = created.json()["id"]
    note_id = client.post(
        f"/api/v1/applications/{application_id}/notes",
        json={"note_type": "OTHER", "body": "Owner only"},
    ).json()["id"]

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B)
    assert client.get("/api/v1/applications").json() == []
    assert client.get(f"/api/v1/applications/{application_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/applications/{application_id}",
            json={"status": "REJECTED"},
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/applications/{application_id}/notes").status_code == 404
    assert (
        client.delete(f"/api/v1/applications/{application_id}/notes/{note_id}").status_code == 404
    )
    assert client.delete(f"/api/v1/applications/{application_id}").status_code == 404

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    assert client.get(f"/api/v1/applications/{application_id}").status_code == 404
    assert client.get(f"/api/v1/applications/{application_id}/notes").status_code == 404
