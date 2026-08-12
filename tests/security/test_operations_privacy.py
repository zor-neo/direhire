from datetime import UTC, datetime

from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import AiOperation, JobWatch, JobWatchRun, OutboxEvent, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def seed_stuck_work(session_factory: sessionmaker[Session]) -> None:
    old = datetime(2020, 1, 1, tzinfo=UTC)
    with session_factory() as database:
        database.add_all(
            [
                User(
                    id=str(USER_A),
                    cognito_subject="operations-owner",
                    email="owner@example.invalid",
                ),
                User(
                    id=str(USER_B),
                    cognito_subject="operations-admin",
                    email="admin@example.invalid",
                    role="SUPERADMIN",
                    mfa_enabled=True,
                ),
            ]
        )
        watch = JobWatch(
            owner_id=str(USER_A),
            name="Private search name",
            target_terms=["Private target"],
            status="ACTIVE",
        )
        database.add(watch)
        database.flush()
        database.add(
            JobWatchRun(
                watch_id=watch.id,
                owner_id=str(USER_A),
                trigger="SCHEDULED",
                status="RUNNING",
                active_marker=watch.id,
                correlation_id="w" * 36,
                created_at=old,
            )
        )
        database.add(
            AiOperation(
                idempotency_key="stuck-private-operation",
                task="CAREER_PREP",
                capability="AI_DEEP_REASONING",
                data_class="SENSITIVE_PRIVATE_DATA",
                status="RUNNING",
                input_hash="h" * 64,
                correlation_id="a" * 36,
                created_at=old,
            )
        )
        database.add(
            OutboxEvent(
                event_id="evt_" + "o" * 32,
                event_type="private.ai.requested",
                correlation_id="o" * 36,
                payload={"artifact_id": "private-id", "private_text": "must-not-leak"},
                occurred_at=old,
            )
        )
        database.commit()


def test_operations_are_superadmin_only_and_metadata_only(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    seed_stuck_work(session_factory)
    assert client.get("/api/v1/admin/operations/summary").status_code == 403
    assert client.get("/api/v1/admin/operations/stuck").status_code == 403

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    summary = client.get("/api/v1/admin/operations/summary")
    stuck = client.get("/api/v1/admin/operations/stuck")

    assert summary.status_code == 200
    assert summary.json()["unpublished_outbox"] == 1
    assert stuck.status_code == 200
    assert {item["kind"] for item in stuck.json()} == {
        "OUTBOX",
        "WATCH_RUN",
        "AI_OPERATION",
    }
    response_text = stuck.text
    assert "must-not-leak" not in response_text
    assert "Private search name" not in response_text
    assert "Private target" not in response_text
