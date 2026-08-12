import hashlib
import re
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from direhire.config import Settings
from direhire.entitlements.service import BASE_CV_LIMIT, EntitlementService
from direhire.errors import AppError, NotFoundError
from direhire.files.extraction import CvTextExtractor
from direhire.files.storage import PresignedUpload, PrivateObjectStorage
from direhire.files.validation import (
    ALLOWED_UPLOAD_TYPES,
    FileValidationFailure,
    MalwareScanner,
    validate_file_structure,
)
from direhire.models import BaseCv, OutboxEvent, PrivateFile, utcnow

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._() -]+")


class CvService:
    def __init__(self, session: Session, storage: PrivateObjectStorage, settings: Settings) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings

    def initiate_upload(
        self,
        *,
        user_id: str,
        plan: str,
        name: str,
        filename: str,
        content_type: str,
        size: int,
    ) -> tuple[BaseCv, PrivateFile, PresignedUpload]:
        clean_filename = self._validate_upload(filename, content_type, size)
        current_usage = int(
            self.session.scalar(
                select(func.count())
                .select_from(BaseCv)
                .where(BaseCv.user_id == user_id, BaseCv.status != "REJECTED")
            )
            or 0
        )
        EntitlementService(self.session).require_capacity(
            user_id=user_id,
            plan=plan,
            entitlement_key=BASE_CV_LIMIT,
            current_usage=current_usage,
        )
        file_id = str(uuid.uuid4())
        extension = ALLOWED_UPLOAD_TYPES[content_type]
        object_key = f"users/{user_id}/cvs/quarantine/{file_id}{extension}"
        private_file = PrivateFile(
            id=file_id,
            owner_id=user_id,
            purpose="BASE_CV",
            bucket=self.settings.private_bucket_name,
            object_key=object_key,
            original_filename=clean_filename,
            declared_content_type=content_type,
            declared_size=size,
        )
        cv = BaseCv(user_id=user_id, file_id=file_id, name=name)
        self.session.add_all((private_file, cv))
        self.session.flush()
        try:
            upload = self.storage.create_upload(
                bucket=private_file.bucket,
                key=private_file.object_key,
                content_type=content_type,
                max_bytes=self.settings.private_upload_max_bytes,
            )
        except Exception as exc:
            self.session.rollback()
            raise AppError(
                "UPLOAD_UNAVAILABLE",
                "A private upload cannot be started right now.",
                503,
                retryable=True,
            ) from exc
        self.session.commit()
        return cv, private_file, upload

    def complete_upload(self, cv_id: str, user_id: str, correlation_id: str) -> BaseCv:
        cv, private_file = self._owned(cv_id, user_id)
        if private_file.status != "UPLOADING":
            return cv
        try:
            metadata = self.storage.head(bucket=private_file.bucket, key=private_file.object_key)
        except Exception as exc:
            raise AppError(
                "UPLOAD_NOT_FOUND",
                "The uploaded file is not available.",
                409,
                retryable=True,
            ) from exc
        if (
            metadata.size != private_file.declared_size
            or metadata.size <= 0
            or metadata.size > self.settings.private_upload_max_bytes
            or metadata.content_type != private_file.declared_content_type
        ):
            private_file.status = "REJECTED"
            private_file.rejection_code = "UPLOAD_METADATA_MISMATCH"
            cv.status = "REJECTED"
            private_file.updated_at = utcnow()
            cv.updated_at = utcnow()
            self.session.commit()
            return cv
        private_file.actual_size = metadata.size
        private_file.status = "QUARANTINED"
        private_file.updated_at = utcnow()
        cv.status = "SCANNING"
        cv.updated_at = utcnow()
        self.session.add(
            OutboxEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_type="file.scan.requested",
                schema_version=1,
                correlation_id=correlation_id,
                payload={"file_id": private_file.id, "cv_id": cv.id},
            )
        )
        self.session.commit()
        return cv

    def list(self, user_id: str) -> list[BaseCv]:
        return list(
            self.session.scalars(
                select(BaseCv).where(BaseCv.user_id == user_id).order_by(BaseCv.created_at)
            )
        )

    def download(self, cv_id: str, user_id: str) -> str:
        cv, private_file = self._owned(cv_id, user_id)
        if cv.status != "ACTIVE" or private_file.status != "CLEAN":
            raise AppError("FILE_NOT_CLEAN", "This file is not available for download.", 409)
        return self.storage.create_download(
            bucket=private_file.bucket,
            key=private_file.object_key,
            filename=private_file.original_filename,
            expires_seconds=self.settings.private_download_url_seconds,
        )

    def delete(self, cv_id: str, user_id: str) -> None:
        cv, private_file = self._owned(cv_id, user_id)
        try:
            self.storage.delete(bucket=private_file.bucket, key=private_file.object_key)
        except Exception as exc:
            raise AppError(
                "FILE_DELETE_FAILED",
                "The file could not be deleted yet.",
                503,
                retryable=True,
            ) from exc
        self.session.delete(cv)
        self.session.delete(private_file)
        self.session.commit()

    def _owned(self, cv_id: str, user_id: str) -> tuple[BaseCv, PrivateFile]:
        row = self.session.execute(
            select(BaseCv, PrivateFile)
            .join(PrivateFile, PrivateFile.id == BaseCv.file_id)
            .where(BaseCv.id == cv_id, BaseCv.user_id == user_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError()
        return row

    def _validate_upload(self, filename: str, content_type: str, size: int) -> str:
        if content_type not in ALLOWED_UPLOAD_TYPES:
            raise AppError("FILE_TYPE_UNSUPPORTED", "Upload a PDF or DOCX file.", 422)
        basename = Path(filename).name
        clean = SAFE_FILENAME.sub("_", basename).strip(" .")
        if not clean or len(clean) > 255 or clean.casefold().endswith((".docm", ".dotm")):
            raise AppError("FILENAME_INVALID", "The filename is invalid.", 422)
        if not clean.casefold().endswith(ALLOWED_UPLOAD_TYPES[content_type]):
            raise AppError("FILE_TYPE_MISMATCH", "The filename and file type do not match.", 422)
        if size <= 0 or size > self.settings.private_upload_max_bytes:
            raise AppError("FILE_SIZE_INVALID", "The file size is not allowed.", 422)
        return clean


class FileScanService:
    def __init__(
        self,
        session: Session,
        storage: PrivateObjectStorage,
        scanner: MalwareScanner,
        settings: Settings,
        extractor: CvTextExtractor | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.scanner = scanner
        self.settings = settings
        self.extractor = extractor

    def process(self, file_id: str) -> PrivateFile:
        private_file = self.session.get(PrivateFile, file_id)
        if private_file is None:
            raise AppError("FILE_NOT_FOUND", "The file no longer exists.", 404)
        if private_file.status in {"CLEAN", "REJECTED"}:
            return private_file
        if private_file.status not in {"QUARANTINED", "SCANNING"}:
            raise AppError("FILE_NOT_READY", "The file is not ready for scanning.", 409)
        private_file.status = "SCANNING"
        private_file.updated_at = utcnow()
        self.session.commit()
        try:
            content = self.storage.read(
                bucket=private_file.bucket,
                key=private_file.object_key,
                max_bytes=self.settings.private_upload_max_bytes,
            )
            detected_type = validate_file_structure(content, private_file.declared_content_type)
            result = self.scanner.scan(content)
        except Exception as exc:
            if isinstance(exc, FileValidationFailure):
                return self._reject(private_file, exc.code)
            private_file.status = "QUARANTINED"
            private_file.updated_at = utcnow()
            self.session.commit()
            raise
        private_file.detected_content_type = detected_type
        private_file.scan_engine = result.engine
        private_file.scan_version = result.version
        if not result.clean:
            return self._reject(private_file, "MALWARE_DETECTED")
        private_file.content_hash = hashlib.sha256(content).hexdigest()
        extension = ALLOWED_UPLOAD_TYPES[detected_type]
        destination_key = (
            f"users/{private_file.owner_id}/cvs/originals/{private_file.id}{extension}"
        )
        self.storage.promote(
            bucket=private_file.bucket,
            source_key=private_file.object_key,
            destination_key=destination_key,
        )
        private_file.object_key = destination_key
        private_file.status = "CLEAN"
        private_file.rejection_code = None
        private_file.updated_at = utcnow()
        cv = self.session.scalar(select(BaseCv).where(BaseCv.file_id == private_file.id))
        if cv is not None:
            cv.status = "ACTIVE"
            if self.extractor is not None:
                try:
                    cv.extracted_text = self.extractor.extract(content, detected_type)
                    cv.extraction_status = "SUCCEEDED"
                except Exception:
                    cv.extracted_text = None
                    cv.extraction_status = "FAILED"
            cv.updated_at = utcnow()
        self.session.commit()
        return private_file

    def _reject(self, private_file: PrivateFile, code: str) -> PrivateFile:
        private_file.status = "REJECTED"
        private_file.rejection_code = code
        private_file.updated_at = utcnow()
        cv = self.session.scalar(select(BaseCv).where(BaseCv.file_id == private_file.id))
        if cv is not None:
            cv.status = "REJECTED"
            cv.updated_at = utcnow()
        self.session.commit()
        return private_file
