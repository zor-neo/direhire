from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from direhire.config import Settings
from direhire.errors import AppError, NotFoundError
from direhire.files.storage import PrivateObjectStorage
from direhire.models import (
    AccountActivity,
    AdHocJobAnalysis,
    Application,
    ApplicationNote,
    AuthSession,
    BaseCv,
    DataExport,
    DeletionWorkflow,
    ExternalNotificationDelivery,
    InAppNotification,
    InterviewRecord,
    Job,
    JobWatch,
    JobWatchRun,
    NotificationDigest,
    NotificationPreference,
    OutboxEvent,
    PrivateAiArtifact,
    PrivateFile,
    ProfessionalProfile,
    ProfileSuggestion,
    Reminder,
    SourceFetch,
    TailoredCvDocument,
    User,
    UserEntitlementOverride,
    UserJob,
    UserSchedule,
    WatchMatch,
    WatchSource,
    utcnow,
)

EXPORT_LIFETIME = timedelta(hours=24)


class PrivacyWorkflowService:
    def __init__(self, session: Session, storage: PrivateObjectStorage, settings: Settings) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings

    def request_export(self, user_id: str, correlation_id: str) -> DataExport:
        now = datetime.now(UTC)
        existing = self.session.scalar(
            select(DataExport)
            .where(
                DataExport.user_id == user_id,
                (DataExport.active_marker == user_id)
                | ((DataExport.status == "SUCCEEDED") & (DataExport.expires_at > now)),
            )
            .order_by(DataExport.created_at.desc())
        )
        if existing is not None:
            return existing
        export = DataExport(user_id=user_id, active_marker=user_id)
        self.session.add(export)
        self.session.flush()
        self.session.add(
            OutboxEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_type="privacy.export.requested",
                schema_version=1,
                correlation_id=correlation_id,
                payload={"export_id": export.id, "user_id": user_id},
            )
        )
        self.session.commit()
        return export

    def list_exports(self, user_id: str) -> list[DataExport]:
        return list(
            self.session.scalars(
                select(DataExport)
                .where(DataExport.user_id == user_id)
                .order_by(DataExport.created_at.desc())
            )
        )

    def download_export(self, export_id: str, user_id: str) -> str:
        export = self.session.scalar(
            select(DataExport).where(DataExport.id == export_id, DataExport.user_id == user_id)
        )
        if export is None:
            raise NotFoundError()
        now = datetime.now(UTC)
        expires_at = export.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if (
            export.status != "SUCCEEDED"
            or export.file_id is None
            or not expires_at
            or expires_at <= now
        ):
            raise AppError("EXPORT_NOT_READY", "The export is not available.", 409)
        private_file = self.session.scalar(
            select(PrivateFile).where(
                PrivateFile.id == export.file_id,
                PrivateFile.owner_id == user_id,
                PrivateFile.status == "CLEAN",
            )
        )
        if private_file is None:
            raise AppError("EXPORT_NOT_READY", "The export is not available.", 409)
        return self.storage.create_download(
            bucket=private_file.bucket,
            key=private_file.object_key,
            filename=private_file.original_filename,
            expires_seconds=self.settings.private_download_url_seconds,
        )

    def request_deletion(
        self, user_id: str, *, scope: str, correlation_id: str
    ) -> DeletionWorkflow:
        marker = f"{user_id}:{scope}"
        existing = self.session.scalar(
            select(DeletionWorkflow).where(DeletionWorkflow.active_marker == marker)
        )
        if existing is not None:
            return existing
        user = self.session.get(User, user_id)
        if user is None:
            raise NotFoundError()
        workflow = DeletionWorkflow(
            user_id=user_id,
            scope=scope,
            active_marker=marker,
            progress={"requested": True},
        )
        self.session.add(workflow)
        if scope == "ACCOUNT":
            user.account_status = "DELETION_PENDING"
            user.security_version += 1
            self.session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
        for watch in self.session.scalars(
            select(JobWatch).where(JobWatch.owner_id == user_id, JobWatch.status == "ACTIVE")
        ):
            watch.status = "PAUSED"
            watch.updated_at = utcnow()
        self.session.flush()
        self.session.add(
            OutboxEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_type="privacy.deletion.requested",
                schema_version=1,
                correlation_id=correlation_id,
                payload={"workflow_id": workflow.id, "user_id": user_id, "scope": scope},
            )
        )
        self.session.commit()
        return workflow

    def list_deletions(self, user_id: str) -> list[DeletionWorkflow]:
        return list(
            self.session.scalars(
                select(DeletionWorkflow)
                .where(DeletionWorkflow.user_id == user_id)
                .order_by(DeletionWorkflow.created_at.desc())
            )
        )


class ExportProcessor:
    def __init__(self, session: Session, storage: PrivateObjectStorage, settings: Settings) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings

    def process(self, export_id: str) -> DataExport:
        export = self.session.get(DataExport, export_id)
        if export is None:
            raise AppError("EXPORT_NOT_FOUND", "The export no longer exists.", 404)
        if export.status == "SUCCEEDED":
            return export
        export.status = "RUNNING"
        export.error_code = None
        self.session.commit()
        try:
            archive = self._build_archive(export.user_id)
            object_key = f"users/{export.user_id}/exports/{export.id}.zip"
            self.storage.write(
                bucket=self.settings.private_bucket_name,
                key=object_key,
                content=archive,
                content_type="application/zip",
            )
        except Exception as exc:
            export.status = "RETRYABLE_FAILED"
            export.error_code = "EXPORT_GENERATION_FAILED"
            self.session.commit()
            raise AppError(
                "EXPORT_GENERATION_FAILED",
                "The export could not be generated yet.",
                503,
                retryable=True,
            ) from exc
        private_file = PrivateFile(
            owner_id=export.user_id,
            purpose="DATA_EXPORT",
            bucket=self.settings.private_bucket_name,
            object_key=object_key,
            original_filename=f"direhire-export-{export.id}.zip",
            declared_content_type="application/zip",
            detected_content_type="application/zip",
            declared_size=len(archive),
            actual_size=len(archive),
            content_hash=hashlib.sha256(archive).hexdigest(),
            status="CLEAN",
            scan_engine="PLATFORM_GENERATED",
            scan_version="1",
        )
        self.session.add(private_file)
        self.session.flush()
        export.file_id = private_file.id
        export.status = "SUCCEEDED"
        export.active_marker = None
        export.expires_at = utcnow() + EXPORT_LIFETIME
        export.completed_at = utcnow()
        self.session.commit()
        return export

    def _build_archive(self, user_id: str) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            user = self.session.get(User, user_id)
            if user is None:
                raise ValueError("user does not exist")
            self._write_json(
                archive,
                "account.json",
                {"email": user.email, "plan": user.plan, "created_at": user.created_at},
            )
            profile = self.session.get(ProfessionalProfile, user_id)
            self._write_json(
                archive,
                "professional-profile.json",
                self._columns(profile) if profile is not None else None,
            )
            applications = list(
                self.session.scalars(select(Application).where(Application.user_id == user_id))
            )
            self._write_csv(
                archive,
                "applications.csv",
                [self._columns(application) for application in applications],
            )
            application_ids = [application.id for application in applications]
            self._write_json(
                archive,
                "application-details.json",
                {
                    "notes": self._rows(
                        ApplicationNote, ApplicationNote.application_id, application_ids
                    ),
                    "interviews": self._rows(
                        InterviewRecord, InterviewRecord.application_id, application_ids
                    ),
                    "reminders": self._rows(Reminder, Reminder.application_id, application_ids),
                },
            )
            self._write_json(
                archive,
                "job-watches.json",
                [
                    self._columns(row)
                    for row in self.session.scalars(
                        select(JobWatch).where(JobWatch.owner_id == user_id)
                    )
                ],
            )
            saved_rows = self.session.execute(
                select(UserJob, Job)
                .join(Job, Job.id == UserJob.job_id)
                .where(UserJob.user_id == user_id)
            )
            self._write_csv(
                archive,
                "saved-jobs.csv",
                [
                    {
                        "status": user_job.status,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location_raw,
                    }
                    for user_job, job in saved_rows
                ],
            )
            preference = self.session.get(NotificationPreference, user_id)
            self._write_json(
                archive,
                "notification-preference.json",
                self._columns(preference) if preference is not None else None,
            )
            artifacts = list(
                self.session.scalars(
                    select(PrivateAiArtifact).where(PrivateAiArtifact.user_id == user_id)
                )
            )
            self._write_json(
                archive,
                "private-ai-artifacts.json",
                [
                    {
                        "id": artifact.id,
                        "artifact_type": artifact.artifact_type,
                        "job_id": artifact.job_id,
                        "cv_id": artifact.cv_id,
                        "status": artifact.status,
                        "content": artifact.content,
                        "working_draft": artifact.working_draft,
                        "error_code": artifact.error_code,
                        "created_at": artifact.created_at,
                        "updated_at": artifact.updated_at,
                    }
                    for artifact in artifacts
                ],
            )
            self._write_json(
                archive,
                "profile-suggestions.json",
                [
                    self._columns(suggestion)
                    for suggestion in self.session.scalars(
                        select(ProfileSuggestion).where(ProfileSuggestion.user_id == user_id)
                    )
                ],
            )
            self._write_json(
                archive,
                "analyze-a-job.json",
                [
                    self._columns(analysis)
                    for analysis in self.session.scalars(
                        select(AdHocJobAnalysis).where(AdHocJobAnalysis.user_id == user_id)
                    )
                ],
            )
            cvs = self.session.execute(
                select(BaseCv, PrivateFile)
                .join(PrivateFile, PrivateFile.id == BaseCv.file_id)
                .where(
                    BaseCv.user_id == user_id,
                    BaseCv.status == "ACTIVE",
                    PrivateFile.status == "CLEAN",
                )
            )
            total_files = 0
            for cv, private_file in cvs:
                content = self.storage.read(
                    bucket=private_file.bucket,
                    key=private_file.object_key,
                    max_bytes=self.settings.private_upload_max_bytes,
                )
                total_files += len(content)
                if total_files > 50_000_000:
                    raise ValueError("export file limit exceeded")
                archive.writestr(f"cvs/{cv.id}-{private_file.original_filename}", content)
            tailored_documents = self.session.execute(
                select(TailoredCvDocument, PrivateFile)
                .join(PrivateFile, PrivateFile.id == TailoredCvDocument.file_id)
                .where(
                    TailoredCvDocument.user_id == user_id,
                    TailoredCvDocument.status == "SUCCEEDED",
                    PrivateFile.status == "CLEAN",
                )
            )
            for document, private_file in tailored_documents:
                content = self.storage.read(
                    bucket=private_file.bucket,
                    key=private_file.object_key,
                    max_bytes=self.settings.private_upload_max_bytes,
                )
                total_files += len(content)
                if total_files > 50_000_000:
                    raise ValueError("export file limit exceeded")
                archive.writestr(
                    f"tailored-cvs/{document.artifact_id}/{private_file.original_filename}",
                    content,
                )
        return output.getvalue()

    def _rows(self, model: type, column: object, ids: list[str]) -> list[dict[str, object]]:
        if not ids:
            return []
        return [
            self._columns(row)
            for row in self.session.scalars(select(model).where(column.in_(ids)))  # type: ignore[attr-defined]
        ]

    @staticmethod
    def _columns(instance: object) -> dict[str, object]:
        return {
            column.name: getattr(instance, column.name)
            for column in instance.__table__.columns  # type: ignore[attr-defined]
            if column.name not in {"user_id", "owner_id"}
        }

    @staticmethod
    def _write_json(archive: zipfile.ZipFile, name: str, value: object) -> None:
        archive.writestr(name, json.dumps(value, default=str, ensure_ascii=False, indent=2))

    @staticmethod
    def _write_csv(archive: zipfile.ZipFile, name: str, rows: list[dict[str, object]]) -> None:
        buffer = io.StringIO(newline="")
        fieldnames = sorted({key for row in rows for key in row})
        if fieldnames:
            writer = csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        archive.writestr(name, buffer.getvalue())


class DeletionProcessor:
    def __init__(self, session: Session, storage: PrivateObjectStorage) -> None:
        self.session = session
        self.storage = storage

    def process(self, workflow_id: str) -> DeletionWorkflow:
        workflow = self.session.get(DeletionWorkflow, workflow_id)
        if workflow is None:
            raise AppError("DELETION_NOT_FOUND", "The deletion workflow was not found.", 404)
        if workflow.status == "SUCCEEDED":
            return workflow
        workflow.status = "RUNNING"
        workflow.error_code = None
        workflow.progress = {**workflow.progress, "storage_started": True}
        self.session.commit()
        files = list(
            self.session.scalars(
                select(PrivateFile).where(PrivateFile.owner_id == workflow.user_id)
            )
        )
        try:
            for private_file in files:
                self.storage.delete(bucket=private_file.bucket, key=private_file.object_key)
        except Exception as exc:
            workflow.status = "RETRYABLE_FAILED"
            workflow.error_code = "PRIVATE_STORAGE_DELETE_FAILED"
            self.session.commit()
            raise AppError(
                "PRIVATE_STORAGE_DELETE_FAILED",
                "Private data deletion is still in progress.",
                503,
                retryable=True,
            ) from exc
        self._delete_private_rows(workflow.user_id)
        if workflow.scope == "ACCOUNT":
            user = self.session.get(User, workflow.user_id)
            if user is not None:
                tombstone = uuid.uuid4().hex
                user.email = f"deleted+{tombstone}@example.invalid"
                user.cognito_subject = f"deleted-{tombstone}"
                user.role = "USER"
                user.plan = "FREE"
                user.mfa_enabled = False
                user.account_status = "DELETED"
                user.security_version += 1
        workflow.status = "SUCCEEDED"
        workflow.active_marker = None
        workflow.error_code = None
        workflow.progress = {
            "storage_deleted": True,
            "active_private_data_deleted": True,
            "account_anonymized": workflow.scope == "ACCOUNT",
        }
        workflow.completed_at = utcnow()
        self.session.commit()
        return workflow

    def _delete_private_rows(self, user_id: str) -> None:
        application_ids = list(
            self.session.scalars(select(Application.id).where(Application.user_id == user_id))
        )
        if application_ids:
            self.session.execute(
                delete(ApplicationNote).where(ApplicationNote.application_id.in_(application_ids))
            )
            self.session.execute(
                delete(InterviewRecord).where(InterviewRecord.application_id.in_(application_ids))
            )
            self.session.execute(
                delete(Reminder).where(Reminder.application_id.in_(application_ids))
            )
        self.session.execute(delete(Application).where(Application.user_id == user_id))
        digest_ids = list(
            self.session.scalars(
                select(NotificationDigest.id).where(NotificationDigest.user_id == user_id)
            )
        )
        if digest_ids:
            self.session.execute(
                delete(ExternalNotificationDelivery).where(
                    ExternalNotificationDelivery.digest_id.in_(digest_ids)
                )
            )
            self.session.execute(
                delete(InAppNotification).where(InAppNotification.digest_id.in_(digest_ids))
            )
        self.session.execute(
            delete(NotificationDigest).where(NotificationDigest.user_id == user_id)
        )
        watch_ids = list(
            self.session.scalars(select(JobWatch.id).where(JobWatch.owner_id == user_id))
        )
        run_ids: list[str] = []
        if watch_ids:
            run_ids = list(
                self.session.scalars(
                    select(JobWatchRun.id).where(JobWatchRun.watch_id.in_(watch_ids))
                )
            )
            if run_ids:
                self.session.execute(delete(SourceFetch).where(SourceFetch.run_id.in_(run_ids)))
                self.session.execute(delete(WatchMatch).where(WatchMatch.run_id.in_(run_ids)))
            self.session.execute(delete(JobWatchRun).where(JobWatchRun.watch_id.in_(watch_ids)))
            self.session.execute(delete(WatchSource).where(WatchSource.watch_id.in_(watch_ids)))
        self.session.execute(delete(JobWatch).where(JobWatch.owner_id == user_id))
        artifact_ids = list(
            self.session.scalars(
                select(PrivateAiArtifact.id).where(PrivateAiArtifact.user_id == user_id)
            )
        )
        self.session.execute(delete(AdHocJobAnalysis).where(AdHocJobAnalysis.user_id == user_id))
        if artifact_ids:
            self.session.execute(
                delete(TailoredCvDocument).where(TailoredCvDocument.artifact_id.in_(artifact_ids))
            )
            self.session.execute(
                delete(ProfileSuggestion).where(ProfileSuggestion.artifact_id.in_(artifact_ids))
            )
        self.session.execute(delete(PrivateAiArtifact).where(PrivateAiArtifact.user_id == user_id))
        self.session.execute(delete(BaseCv).where(BaseCv.user_id == user_id))
        self.session.execute(delete(DataExport).where(DataExport.user_id == user_id))
        self.session.execute(delete(PrivateFile).where(PrivateFile.owner_id == user_id))
        self.session.execute(
            delete(ProfessionalProfile).where(ProfessionalProfile.user_id == user_id)
        )
        self.session.execute(delete(UserJob).where(UserJob.user_id == user_id))
        self.session.execute(
            delete(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        self.session.execute(delete(UserSchedule).where(UserSchedule.user_id == user_id))
        self.session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
        self.session.execute(delete(AccountActivity).where(AccountActivity.user_id == user_id))
        self.session.execute(
            delete(UserEntitlementOverride).where(UserEntitlementOverride.user_id == user_id)
        )
        for event in self.session.scalars(select(OutboxEvent)):
            if event.payload.get("owner_id") == user_id or event.payload.get("user_id") == user_id:
                self.session.delete(event)
