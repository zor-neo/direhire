from direhire.auth import CurrentUser, current_user
from direhire.files.storage import get_private_storage
from direhire.main import app
from direhire.models import PrivateAiArtifact, User
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


def seed_artifact(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as database:
        database.add_all(
            [
                User(
                    id=str(USER_A),
                    cognito_subject="artifact-owner",
                    email="owner@example.invalid",
                ),
                User(
                    id=str(USER_B),
                    cognito_subject="artifact-other",
                    email="other@example.invalid",
                ),
            ]
        )
        artifact = PrivateAiArtifact(
            user_id=str(USER_A),
            artifact_type="PROFILE_FIT",
            idempotency_key="owner-artifact",
            status="SUCCEEDED",
            input_hash="a" * 64,
            input_snapshot={"profile": {"headline": "private"}},
            content={"summary": "owner only"},
            working_draft={"summary": "owner draft"},
        )
        database.add(artifact)
        database.commit()
        return artifact.id


def test_private_ai_artifacts_are_owner_only(
    client: object, session_factory: sessionmaker[Session]
) -> None:
    app.dependency_overrides[get_private_storage] = lambda: object()
    artifact_id = seed_artifact(session_factory)

    owner_response = client.get(f"/api/v1/private-ai/artifacts/{artifact_id}")  # type: ignore[attr-defined]
    assert owner_response.status_code == 200
    assert "input_snapshot" not in owner_response.json()

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B)
    assert client.get("/api/v1/private-ai/artifacts").json() == []  # type: ignore[attr-defined]
    assert client.get(f"/api/v1/private-ai/artifacts/{artifact_id}").status_code == 404  # type: ignore[attr-defined]
    assert (
        client.patch(  # type: ignore[attr-defined]
            f"/api/v1/private-ai/artifacts/{artifact_id}/draft",
            json={"working_draft": {"summary": "stolen"}},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/private-ai/artifacts/{artifact_id}").status_code == 404  # type: ignore[attr-defined]

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="ADMIN")
    assert client.get(f"/api/v1/private-ai/artifacts/{artifact_id}").status_code == 404  # type: ignore[attr-defined]

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A)
    assert client.get(f"/api/v1/private-ai/artifacts/{artifact_id}").status_code == 200  # type: ignore[attr-defined]
