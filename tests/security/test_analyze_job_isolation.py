import json

from direhire.auth import CurrentUser, current_user
from direhire.main import app
from direhire.models import AdHocJobAnalysis, PrivateAiArtifact, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B
from tests.integration.test_public_ai_orchestrator import valid_content


def seed_analysis(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as database:
        database.add_all(
            [
                User(
                    id=str(USER_A),
                    cognito_subject="analysis-owner",
                    email="analysis-owner@example.invalid",
                ),
                User(
                    id=str(USER_B),
                    cognito_subject="analysis-other",
                    email="analysis-other@example.invalid",
                ),
            ]
        )
        artifact = PrivateAiArtifact(
            user_id=str(USER_A),
            artifact_type="PASTED_JOB_ANALYSIS",
            idempotency_key="private-pasted-analysis",
            status="SUCCEEDED",
            input_hash="x" * 64,
            input_snapshot={"job_description": "owner private JD"},
            content=json.loads(valid_content()),
        )
        database.add(artifact)
        database.flush()
        row = AdHocJobAnalysis(
            user_id=str(USER_A),
            input_type="PASTED_TEXT",
            idempotency_key="owner-analysis",
            private_text="owner private JD",
            private_artifact_id=artifact.id,
            status="ANALYSIS_QUEUED",
        )
        database.add(row)
        database.commit()
        return row.id


def test_analyze_job_is_owner_only(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    analysis_id = seed_analysis(session_factory)
    assert client.get(f"/api/v1/analyze-jobs/{analysis_id}").status_code == 200

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B)
    assert client.get("/api/v1/analyze-jobs").json() == []
    assert client.get(f"/api/v1/analyze-jobs/{analysis_id}").status_code == 404
    assert client.post(f"/api/v1/analyze-jobs/{analysis_id}/save").status_code == 404
    assert client.post(f"/api/v1/analyze-jobs/{analysis_id}/watch-draft").status_code == 404
    assert client.delete(f"/api/v1/analyze-jobs/{analysis_id}").status_code == 404

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    assert client.get(f"/api/v1/analyze-jobs/{analysis_id}").status_code == 404
