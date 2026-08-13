from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from direhire.ai.private_contracts import TailoredCvResult
from direhire.ai.private_service import PrivateAiRequestService
from direhire.config import Settings
from direhire.errors import AppError, NotFoundError
from direhire.files.storage import PrivateObjectStorage
from direhire.models import (
    OutboxEvent,
    PrivateAiArtifact,
    PrivateFile,
    TailoredCvDocument,
    utcnow,
)
from direhire.operations.controls import PlatformControlService

if TYPE_CHECKING:
    from direhire.documents.ats_cv import AtsCvRenderer

DocumentFormat = Literal["DOCX", "PDF"]


class TailoredCvService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def update_metadata(
        self,
        artifact_id: str,
        user_id: str,
        *,
        name: str | None,
        archived: bool | None,
    ) -> PrivateAiArtifact:
        artifact = self._tailored(artifact_id, user_id)
        if name is not None:
            artifact.name = name.strip()
        if archived is not None:
            artifact.archived_at = utcnow() if archived else None
        artifact.updated_at = utcnow()
        self.session.commit()
        return artifact

    def duplicate(self, artifact_id: str, user_id: str, name: str | None) -> PrivateAiArtifact:
        artifact = self._tailored(artifact_id, user_id)
        root_id = artifact.parent_artifact_id or artifact.id
        maximum = (
            self.session.scalar(
                select(func.max(PrivateAiArtifact.version_number)).where(
                    (PrivateAiArtifact.id == root_id)
                    | (PrivateAiArtifact.parent_artifact_id == root_id)
                )
            )
            or 1
        )
        clone = PrivateAiArtifact(
            user_id=user_id,
            artifact_type="TAILORED_CV",
            idempotency_key=f"tailored-copy:{uuid.uuid4().hex}",
            job_id=artifact.job_id,
            cv_id=artifact.cv_id,
            status="SUCCEEDED",
            input_hash=artifact.input_hash,
            input_snapshot=artifact.input_snapshot,
            content=artifact.content,
            working_draft=artifact.working_draft,
            name=(name or artifact.name or "Tailored CV").strip(),
            version_number=maximum + 1,
            parent_artifact_id=root_id,
        )
        self.session.add(clone)
        self.session.commit()
        return clone

    def request_document(
        self,
        artifact_id: str,
        user_id: str,
        format: DocumentFormat,
        correlation_id: str,
    ) -> TailoredCvDocument:
        PlatformControlService(self.session).require(
            "DOCUMENT_GENERATION", "Document generation is temporarily unavailable."
        )
        artifact = self._tailored(artifact_id, user_id)
        if artifact.status != "SUCCEEDED" or artifact.working_draft is None:
            raise AppError("TAILORED_CV_NOT_READY", "The tailored CV is not ready.", 409)
        try:
            TailoredCvResult.model_validate(artifact.working_draft)
        except ValidationError as exc:
            raise AppError(
                "DRAFT_SCHEMA_INVALID", "The working draft has an invalid structure.", 422
            ) from exc
        serialized = json.dumps(artifact.working_draft, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(serialized.encode()).hexdigest()
        existing = self.session.scalar(
            select(TailoredCvDocument).where(
                TailoredCvDocument.artifact_id == artifact.id,
                TailoredCvDocument.format == format,
                TailoredCvDocument.content_hash == content_hash,
            )
        )
        if existing is not None:
            return existing
        document = TailoredCvDocument(
            user_id=user_id,
            artifact_id=artifact.id,
            format=format,
            content_hash=content_hash,
            status="QUEUED",
        )
        self.session.add(document)
        self.session.flush()
        self.session.add(
            OutboxEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_type="private.document.requested",
                schema_version=1,
                correlation_id=correlation_id,
                payload={"document_id": document.id, "user_id": user_id, "format": format},
            )
        )
        self.session.commit()
        return document

    def list_documents(self, artifact_id: str, user_id: str) -> list[TailoredCvDocument]:
        self._tailored(artifact_id, user_id)
        return list(
            self.session.scalars(
                select(TailoredCvDocument)
                .where(
                    TailoredCvDocument.artifact_id == artifact_id,
                    TailoredCvDocument.user_id == user_id,
                )
                .order_by(TailoredCvDocument.created_at.desc())
            )
        )

    def download(
        self,
        document_id: str,
        user_id: str,
        storage: PrivateObjectStorage,
        settings: Settings,
    ) -> str:
        row = self.session.execute(
            select(TailoredCvDocument, PrivateFile)
            .join(PrivateFile, PrivateFile.id == TailoredCvDocument.file_id)
            .where(
                TailoredCvDocument.id == document_id,
                TailoredCvDocument.user_id == user_id,
                TailoredCvDocument.status == "SUCCEEDED",
                PrivateFile.status == "CLEAN",
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError()
        document, private_file = row
        artifact = self._tailored(document.artifact_id, user_id)
        base_name = self._safe_name(artifact.name or "Tailored CV")
        return storage.create_download(
            bucket=private_file.bucket,
            key=private_file.object_key,
            filename=f"{base_name}.{document.format.lower()}",
            expires_seconds=settings.private_download_url_seconds,
        )

    def _tailored(self, artifact_id: str, user_id: str) -> PrivateAiArtifact:
        artifact = PrivateAiRequestService(self.session).get(artifact_id, user_id)
        if artifact.artifact_type != "TAILORED_CV":
            raise NotFoundError()
        return artifact

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._ -]", "", value).strip()[:100] or "Tailored CV"


class TailoredCvDocumentProcessor:
    def __init__(
        self,
        session: Session,
        storage: PrivateObjectStorage,
        settings: Settings,
        renderer: AtsCvRenderer | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        if renderer is None:
            from direhire.documents.ats_cv import AtsCvRenderer

            renderer = AtsCvRenderer()
        self.renderer = renderer

    def process(self, document_id: str) -> TailoredCvDocument:
        document = self.session.get(TailoredCvDocument, document_id)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "The document request was not found.", 404)
        if document.status == "SUCCEEDED":
            return document
        artifact = self.session.scalar(
            select(PrivateAiArtifact).where(
                PrivateAiArtifact.id == document.artifact_id,
                PrivateAiArtifact.user_id == document.user_id,
                PrivateAiArtifact.artifact_type == "TAILORED_CV",
            )
        )
        if artifact is None or artifact.working_draft is None:
            document.status = "PERMANENT_FAILED"
            document.error_code = "TAILORED_CV_NOT_FOUND"
            self.session.commit()
            return document
        document.status = "RUNNING"
        self.session.commit()
        try:
            content = self.renderer.render(artifact.working_draft, document.format)
        except (ValueError, TypeError):
            document.status = "PERMANENT_FAILED"
            document.error_code = "DOCUMENT_CONTENT_INVALID"
            document.completed_at = utcnow()
            self.session.commit()
            return document
        extension = document.format.lower()
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if document.format == "DOCX"
            else "application/pdf"
        )
        key = f"users/{document.user_id}/tailored/{artifact.id}/{document.id}.{extension}"
        self.storage.write(
            bucket=self.settings.private_bucket_name,
            key=key,
            content=content,
            content_type=content_type,
        )
        private_file = PrivateFile(
            owner_id=document.user_id,
            purpose="TAILORED_CV",
            bucket=self.settings.private_bucket_name,
            object_key=key,
            original_filename=f"tailored-cv.{extension}",
            declared_content_type=content_type,
            detected_content_type=content_type,
            declared_size=len(content),
            actual_size=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            status="CLEAN",
            scan_engine="GENERATED_TRUSTED",
        )
        self.session.add(private_file)
        self.session.flush()
        document.file_id = private_file.id
        document.status = "SUCCEEDED"
        document.error_code = None
        document.completed_at = utcnow()
        self.session.commit()
        return document
