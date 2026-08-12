import io
import zipfile
from datetime import UTC, datetime, timedelta

from direhire.auth import CurrentUser, current_user
from direhire.config import get_settings
from direhire.files.storage import PresignedUpload, StoredObjectMetadata, get_private_storage
from direhire.main import app
from direhire.models import (
    Application,
    ApplicationNote,
    AuditEvent,
    AuthSession,
    BaseCv,
    DeletionWorkflow,
    Job,
    PrivateAiArtifact,
    PrivateFile,
    ProfessionalProfile,
    ProfileSuggestion,
    User,
    UserJob,
)
from direhire.privacy.service import DeletionProcessor, ExportProcessor
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.downloads: list[str] = []
        self.deletes: list[str] = []

    def create_upload(
        self, *, bucket: str, key: str, content_type: str, max_bytes: int
    ) -> PresignedUpload:
        del bucket, max_bytes
        return PresignedUpload("https://upload.example.invalid", {"key": key, "type": content_type})

    def head(self, *, bucket: str, key: str) -> StoredObjectMetadata:
        del bucket
        content, content_type = self.objects[key]
        return StoredObjectMetadata(len(content), content_type)

    def read(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
        del bucket
        content = self.objects[key][0]
        if len(content) > max_bytes:
            raise ValueError("too large")
        return content

    def create_download(self, *, bucket: str, key: str, filename: str, expires_seconds: int) -> str:
        del bucket, filename, expires_seconds
        self.downloads.append(key)
        return "https://download.example.invalid/private"

    def delete(self, *, bucket: str, key: str) -> None:
        del bucket
        self.deletes.append(key)
        self.objects.pop(key, None)

    def promote(self, *, bucket: str, source_key: str, destination_key: str) -> None:
        del bucket
        self.objects[destination_key] = self.objects[source_key]

    def write(self, *, bucket: str, key: str, content: bytes, content_type: str) -> None:
        del bucket
        self.objects[key] = (content, content_type)


def seed_private_data(session_factory: sessionmaker[Session], storage: MemoryStorage) -> str:
    with session_factory() as database:
        user_a = User(
            id=str(USER_A), cognito_subject="privacy-a", email="privacy-a@example.invalid"
        )
        user_b = User(
            id=str(USER_B), cognito_subject="privacy-b", email="privacy-b@example.invalid"
        )
        job = Job(
            identity_key="d" * 64,
            title="Shared Engineer",
            company="Shared Synthetic Corp",
            location_raw="Remote",
        )
        database.add_all((user_a, user_b, job))
        database.flush()
        database.add_all(
            (
                UserJob(user_id=str(USER_A), job_id=job.id, status="SAVED"),
                UserJob(user_id=str(USER_B), job_id=job.id, status="SAVED"),
                ProfessionalProfile(
                    user_id=str(USER_A),
                    headline="Private headline",
                    competencies=[{"display_name": "Private skill"}],
                    eligibility_work_rights={"authorized_countries": ["Thailand"]},
                ),
            )
        )
        application = Application(user_id=str(USER_A), job_id=job.id, status="APPLIED")
        database.add(application)
        database.flush()
        database.add(
            ApplicationNote(application_id=application.id, note_type="OTHER", body="Private note")
        )
        file = PrivateFile(
            owner_id=str(USER_A),
            purpose="BASE_CV",
            bucket="private",
            object_key=f"users/{USER_A}/cvs/originals/cv.pdf",
            original_filename="Synthetic CV.pdf",
            declared_content_type="application/pdf",
            detected_content_type="application/pdf",
            declared_size=24,
            actual_size=24,
            status="CLEAN",
        )
        database.add(file)
        database.flush()
        cv = BaseCv(user_id=str(USER_A), file_id=file.id, name="Primary", status="ACTIVE")
        database.add(cv)
        database.flush()
        artifact = PrivateAiArtifact(
            user_id=str(USER_A),
            artifact_type="TAILORED_CV",
            idempotency_key="privacy-export-artifact",
            job_id=job.id,
            cv_id=cv.id,
            status="SUCCEEDED",
            input_hash="f" * 64,
            input_snapshot={"cv_text": "Private CV source"},
            content={"title": "Tailored result"},
            working_draft={"title": "User-edited result"},
        )
        database.add(artifact)
        database.flush()
        database.add(
            ProfileSuggestion(
                user_id=str(USER_A),
                artifact_id=artifact.id,
                category="TECHNOLOGY",
                suggestion={"display_name": "FastAPI", "evidence": "Private evidence"},
            )
        )
        database.add(
            AuthSession(
                token_hash="a" * 64,
                csrf_token_hash="b" * 64,
                user_id=str(USER_A),
                expires_at=datetime.now(UTC) + timedelta(days=1),
                last_seen_at=datetime.now(UTC),
                security_version=1,
            )
        )
        database.add(
            AuditEvent(
                actor_user_id=str(USER_A),
                actor_role="USER",
                action="SYNTHETIC_SECURITY_EVENT",
                target_type="ACCOUNT",
                target_id=str(USER_A),
                result="SUCCEEDED",
                correlation_id="e" * 36,
            )
        )
        database.commit()
        storage.objects[file.object_key] = (b"%PDF-1.7\nSynthetic CV\n%%EOF", "application/pdf")
        return job.id


def test_export_is_private_short_lived_complete_and_excludes_audit_internals(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    storage = MemoryStorage()
    seed_private_data(session_factory, storage)
    app.dependency_overrides[get_private_storage] = lambda: storage
    requested = client.post("/api/v1/privacy/exports")
    assert requested.status_code == 202
    export_id = requested.json()["id"]
    assert client.post("/api/v1/privacy/exports").json()["id"] == export_id
    with session_factory() as database:
        export = ExportProcessor(database, storage, get_settings()).process(export_id)
        assert export.status == "SUCCEEDED"
        file = database.get(PrivateFile, export.file_id)
        assert file is not None
        archive_bytes = storage.objects[file.object_key][0]
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        assert "account.json" in names
        assert "professional-profile.json" in names
        assert "applications.csv" in names
        assert "private-ai-artifacts.json" in names
        assert "profile-suggestions.json" in names
        assert any(name.startswith("cvs/") for name in names)
        assert all("audit" not in name for name in names)
        assert b"Private note" in archive.read("application-details.json")
        assert b"User-edited result" in archive.read("private-ai-artifacts.json")
        assert b"Private CV source" not in archive.read("private-ai-artifacts.json")

    assert client.get(f"/api/v1/privacy/exports/{export_id}/download").status_code == 200
    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B)
    assert client.get(f"/api/v1/privacy/exports/{export_id}/download").status_code == 404
    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    assert client.get(f"/api/v1/privacy/exports/{export_id}/download").status_code == 404
    assert len(storage.downloads) == 1


def test_account_deletion_revokes_immediately_then_purges_and_preserves_shared_job(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    storage = MemoryStorage()
    shared_job_id = seed_private_data(session_factory, storage)
    app.dependency_overrides[get_private_storage] = lambda: storage
    invalid = client.post(
        "/api/v1/privacy/deletions",
        json={"scope": "ACCOUNT", "confirmation": "delete"},
    )
    assert invalid.status_code == 422
    requested = client.post(
        "/api/v1/privacy/deletions",
        json={"scope": "ACCOUNT", "confirmation": "DELETE MY ACCOUNT"},
    )
    assert requested.status_code == 202
    workflow_id = requested.json()["id"]
    with session_factory() as database:
        user = database.get(User, str(USER_A))
        assert user is not None and user.account_status == "DELETION_PENDING"
        assert database.scalar(select(func.count()).select_from(AuthSession)) == 0
        completed = DeletionProcessor(database, storage).process(workflow_id)
        repeated = DeletionProcessor(database, storage).process(workflow_id)
        assert completed.status == "SUCCEEDED"
        assert repeated.status == "SUCCEEDED"
        user = database.get(User, str(USER_A))
        assert user is not None
        assert user.account_status == "DELETED"
        assert user.email.endswith("@example.invalid") and not user.email.startswith("privacy-a")
        assert database.scalar(select(func.count()).select_from(ProfessionalProfile)) == 0
        assert database.scalar(select(func.count()).select_from(Application)) == 0
        assert database.scalar(select(func.count()).select_from(PrivateFile)) == 0
        assert database.scalar(select(func.count()).select_from(PrivateAiArtifact)) == 0
        assert database.scalar(select(func.count()).select_from(ProfileSuggestion)) == 0
        assert database.get(Job, shared_job_id) is not None
        assert (
            database.scalar(
                select(func.count())
                .select_from(UserJob)
                .where(UserJob.user_id == str(USER_B), UserJob.job_id == shared_job_id)
            )
            == 1
        )
        assert database.scalar(select(func.count()).select_from(AuditEvent)) == 1
        workflow = database.get(DeletionWorkflow, workflow_id)
        assert workflow is not None and workflow.active_marker is None
    assert storage.objects == {}
