from dataclasses import dataclass

from direhire.auth import CurrentUser, current_user
from direhire.config import get_settings
from direhire.files.service import FileScanService
from direhire.files.storage import (
    PresignedUpload,
    StoredObjectMetadata,
    get_private_storage,
)
from direhire.files.validation import PDF_MIME, ScanResult
from direhire.main import app
from direhire.models import BaseCv, OutboxEvent, PrivateFile, User
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A, USER_B


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.download_calls: list[str] = []
        self.deleted: list[str] = []

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
        self.download_calls.append(key)
        return "https://download.example.invalid/signed"

    def delete(self, *, bucket: str, key: str) -> None:
        del bucket
        self.deleted.append(key)
        self.objects.pop(key, None)

    def promote(self, *, bucket: str, source_key: str, destination_key: str) -> None:
        del bucket
        self.objects[destination_key] = self.objects[source_key]


@dataclass
class FakeScanner:
    clean: bool = True

    def scan(self, content: bytes) -> ScanResult:
        del content
        return ScanResult(self.clean, "TEST_SCANNER", "1")


def seed_users(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as database:
        database.add_all(
            (
                User(id=str(USER_A), cognito_subject="file-user-a", email="a@example.invalid"),
                User(id=str(USER_B), cognito_subject="file-user-b", email="b@example.invalid"),
            )
        )
        database.commit()


def test_cv_upload_scan_download_and_hard_delete_are_owner_only(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    seed_users(session_factory)
    storage = FakeStorage()
    app.dependency_overrides[get_private_storage] = lambda: storage
    content = b"%PDF-1.7\nSynthetic resume\n%%EOF"
    started = client.post(
        "/api/v1/cvs/uploads",
        json={
            "name": "Primary CV",
            "filename": "Alex Resume.pdf",
            "content_type": PDF_MIME,
            "size": len(content),
        },
    )
    assert started.status_code == 201
    assert started.json()["upload_url"] == "https://upload.example.invalid"
    cv_id = started.json()["id"]
    with session_factory() as database:
        cv = database.get(BaseCv, cv_id)
        assert cv is not None
        private_file = database.get(PrivateFile, cv.file_id)
        assert private_file is not None
        storage.objects[private_file.object_key] = (content, PDF_MIME)

    completed = client.post(f"/api/v1/cvs/{cv_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "SCANNING"
    with session_factory() as database:
        private_file = database.scalar(select(PrivateFile))
        event = database.scalar(
            select(OutboxEvent).where(OutboxEvent.event_type == "file.scan.requested")
        )
        assert private_file is not None and event is not None
        FileScanService(database, storage, FakeScanner(), get_settings()).process(private_file.id)

    listed = client.get("/api/v1/cvs")
    assert listed.json()[0]["status"] == "ACTIVE"
    downloaded = client.get(f"/api/v1/cvs/{cv_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.json()["expires_in_seconds"] == 300
    assert len(storage.download_calls) == 1

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B)
    assert client.get("/api/v1/cvs").json() == []
    assert client.get(f"/api/v1/cvs/{cv_id}/download").status_code == 404
    assert client.delete(f"/api/v1/cvs/{cv_id}").status_code == 404
    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    assert client.get(f"/api/v1/cvs/{cv_id}/download").status_code == 404
    assert len(storage.download_calls) == 1

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A)
    assert client.delete(f"/api/v1/cvs/{cv_id}").status_code == 204
    with session_factory() as database:
        assert database.get(BaseCv, cv_id) is None
        assert database.scalar(select(PrivateFile)) is None
    assert storage.deleted


def test_malware_rejection_never_permits_download(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    seed_users(session_factory)
    storage = FakeStorage()
    app.dependency_overrides[get_private_storage] = lambda: storage
    content = b"%PDF-1.7\nSynthetic\n%%EOF"
    cv_id = client.post(
        "/api/v1/cvs/uploads",
        json={
            "name": "Rejected",
            "filename": "Rejected.pdf",
            "content_type": PDF_MIME,
            "size": len(content),
        },
    ).json()["id"]
    with session_factory() as database:
        cv = database.get(BaseCv, cv_id)
        assert cv is not None
        private_file = database.get(PrivateFile, cv.file_id)
        assert private_file is not None
        storage.objects[private_file.object_key] = (content, PDF_MIME)
    client.post(f"/api/v1/cvs/{cv_id}/complete")
    with session_factory() as database:
        private_file = database.scalar(select(PrivateFile))
        assert private_file is not None
        FileScanService(database, storage, FakeScanner(clean=False), get_settings()).process(
            private_file.id
        )
    assert client.get(f"/api/v1/cvs/{cv_id}/download").status_code == 409
    assert storage.download_calls == []


def test_profile_is_optional_replaceable_deletable_and_invisible_to_admin(
    client: TestClient,
) -> None:
    missing = client.get("/api/v1/profile")
    assert missing.status_code == 404
    payload = {
        "headline": "Backend engineer",
        "competencies": [
            {"canonical_id": "python", "display_name": "My exact Python term", "proficiency": 4}
        ],
        "eligibility_work_rights": {
            "citizenships": ["Synthetic Country"],
            "authorized_countries": ["Thailand"],
            "sponsorship_needed": "UNCLEAR",
        },
    }
    assert client.put("/api/v1/profile", json=payload).status_code == 200
    assert (
        client.get("/api/v1/profile").json()["competencies"][0]["display_name"]
        == "My exact Python term"
    )

    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_B, role="SUPERADMIN")
    assert client.get("/api/v1/profile").status_code == 404
    app.dependency_overrides[current_user] = lambda: CurrentUser(USER_A)
    assert client.delete("/api/v1/profile").status_code == 204
    assert client.get("/api/v1/profile").status_code == 404
