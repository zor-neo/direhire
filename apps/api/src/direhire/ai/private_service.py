from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from direhire.ai.private_contracts import PrepareToApplyResult, TailoredCvResult
from direhire.entitlements.service import (
    CV_SUGGESTION_MONTHLY_LIMIT,
    PRIVATE_AI_DAILY_LIMIT,
    EntitlementService,
)
from direhire.errors import AppError, NotFoundError
from direhire.files.storage import PrivateObjectStorage
from direhire.models import (
    AdHocJobAnalysis,
    BaseCv,
    JobDemandProfile,
    JobVersion,
    OutboxEvent,
    PrivateAiArtifact,
    PrivateFile,
    ProfessionalProfile,
    ProfileSuggestion,
    TailoredCvDocument,
    UserJob,
    utcnow,
)
from direhire.operations.controls import PlatformControlService

ArtifactType = Literal[
    "CV_SUGGESTIONS",
    "PROFILE_FIT",
    "TAILORED_CV",
    "PREPARE_TO_APPLY",
    "CAREER_PREP",
    "COMPANY_RESEARCH",
    "PROFESSIONAL_ADVICE",
]

JOB_REQUIRED = {
    "PROFILE_FIT",
    "TAILORED_CV",
    "PREPARE_TO_APPLY",
    "CAREER_PREP",
    "COMPANY_RESEARCH",
    "PROFESSIONAL_ADVICE",
}
CV_REQUIRED = {"CV_SUGGESTIONS", "TAILORED_CV"}


class SuggestionEdit(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    canonical_id: str | None = Field(default=None, max_length=100)
    proficiency: int | None = Field(default=None, ge=1, le=5)


class PrivateAiRequestService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def request(
        self,
        *,
        user_id: str,
        plan: str,
        artifact_type: ArtifactType,
        job_id: str | None,
        cv_id: str | None,
        correlation_id: str,
    ) -> PrivateAiArtifact:
        PlatformControlService(self.session).require(
            "PRIVATE_AI", "Private AI is temporarily unavailable."
        )
        snapshot = self._snapshot(user_id, artifact_type, job_id, cv_id)
        serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        input_hash = hashlib.sha256(serialized.encode()).hexdigest()
        idempotency_key = (
            f"private-ai:{user_id}:{artifact_type}:{job_id or '-'}:{cv_id or '-'}:{input_hash}"
        )
        existing = self.session.scalar(
            select(PrivateAiArtifact).where(PrivateAiArtifact.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        self._require_quota(user_id, plan, artifact_type)
        artifact = PrivateAiArtifact(
            user_id=user_id,
            artifact_type=artifact_type,
            idempotency_key=idempotency_key,
            job_id=job_id,
            cv_id=cv_id,
            status="QUEUED",
            input_hash=input_hash,
            input_snapshot=snapshot,
        )
        self.session.add(artifact)
        self.session.flush()
        self.session.add(
            OutboxEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_type="private.ai.requested",
                schema_version=1,
                correlation_id=correlation_id,
                payload={
                    "artifact_id": artifact.id,
                    "user_id": user_id,
                    "artifact_type": artifact_type,
                },
            )
        )
        self.session.commit()
        return artifact

    def list(self, user_id: str) -> list[PrivateAiArtifact]:
        return list(
            self.session.scalars(
                select(PrivateAiArtifact)
                .where(PrivateAiArtifact.user_id == user_id)
                .order_by(PrivateAiArtifact.created_at.desc())
            )
        )

    def get(self, artifact_id: str, user_id: str) -> PrivateAiArtifact:
        artifact = self.session.scalar(
            select(PrivateAiArtifact).where(
                PrivateAiArtifact.id == artifact_id,
                PrivateAiArtifact.user_id == user_id,
            )
        )
        if artifact is None:
            raise NotFoundError()
        return artifact

    def update_draft(
        self, artifact_id: str, user_id: str, draft: dict[str, object]
    ) -> PrivateAiArtifact:
        artifact = self.get(artifact_id, user_id)
        if artifact.status != "SUCCEEDED":
            raise AppError("ARTIFACT_NOT_READY", "This result is not ready to edit.", 409)
        encoded = json.dumps(draft, separators=(",", ":"))
        if len(encoded.encode()) > 100_000:
            raise AppError("DRAFT_TOO_LARGE", "The working draft is too large.", 413)
        try:
            if artifact.artifact_type == "TAILORED_CV":
                TailoredCvResult.model_validate(draft)
            elif artifact.artifact_type == "PREPARE_TO_APPLY":
                PrepareToApplyResult.model_validate(draft)
        except ValidationError as exc:
            raise AppError(
                "DRAFT_SCHEMA_INVALID", "The working draft has an invalid structure.", 422
            ) from exc
        artifact.working_draft = draft
        artifact.updated_at = utcnow()
        self.session.commit()
        return artifact

    def delete(
        self,
        artifact_id: str,
        user_id: str,
        storage: PrivateObjectStorage | None = None,
    ) -> None:
        artifact = self.get(artifact_id, user_id)
        documents = list(
            self.session.scalars(
                select(TailoredCvDocument).where(
                    TailoredCvDocument.artifact_id == artifact.id,
                    TailoredCvDocument.user_id == user_id,
                )
            )
        )
        for document in documents:
            private_file = (
                self.session.get(PrivateFile, document.file_id) if document.file_id else None
            )
            if private_file is not None:
                if storage is None:
                    raise AppError(
                        "PRIVATE_STORAGE_UNAVAILABLE",
                        "The private document cannot be deleted right now.",
                        503,
                        retryable=True,
                    )
                storage.delete(bucket=private_file.bucket, key=private_file.object_key)
                self.session.delete(private_file)
            self.session.delete(document)
        self.session.execute(
            delete(AdHocJobAnalysis).where(
                AdHocJobAnalysis.private_artifact_id == artifact.id,
                AdHocJobAnalysis.user_id == user_id,
            )
        )
        self.session.delete(artifact)
        self.session.commit()

    def _snapshot(
        self,
        user_id: str,
        artifact_type: ArtifactType,
        job_id: str | None,
        cv_id: str | None,
    ) -> dict[str, object]:
        snapshot: dict[str, object] = {"artifact_type": artifact_type}
        if artifact_type in JOB_REQUIRED:
            if not job_id:
                raise AppError("JOB_REQUIRED", "Select a job for this request.", 422)
            visible = self.session.scalar(
                select(UserJob.id).where(UserJob.user_id == user_id, UserJob.job_id == job_id)
            )
            if visible is None:
                raise NotFoundError()
            demand = self.session.scalar(
                select(JobDemandProfile)
                .join(JobVersion, JobVersion.id == JobDemandProfile.job_version_id)
                .where(
                    JobVersion.job_id == job_id,
                    JobDemandProfile.status == "SUCCEEDED",
                )
                .order_by(JobDemandProfile.updated_at.desc())
            )
            if demand is None or demand.profile is None:
                raise AppError(
                    "JOB_ANALYSIS_NOT_READY",
                    "Structured job analysis is not ready yet.",
                    409,
                    retryable=True,
                )
            snapshot["job_demand_profile"] = demand.profile.get("content", demand.profile)
        if artifact_type in CV_REQUIRED or cv_id:
            if not cv_id:
                raise AppError("CV_REQUIRED", "Select a clean Base CV.", 422)
            cv = self.session.scalar(
                select(BaseCv).where(
                    BaseCv.id == cv_id,
                    BaseCv.user_id == user_id,
                    BaseCv.status == "ACTIVE",
                )
            )
            if cv is None:
                raise NotFoundError()
            if cv.extraction_status != "SUCCEEDED" or not cv.extracted_text:
                raise AppError(
                    "CV_EXTRACTION_NOT_READY",
                    "The selected CV is not ready for private AI.",
                    409,
                    retryable=cv.extraction_status == "PENDING",
                )
            snapshot["cv_text"] = cv.extracted_text
        profile = self.session.get(ProfessionalProfile, user_id)
        if artifact_type == "PROFILE_FIT" and profile is None:
            raise AppError("PROFILE_REQUIRED", "Create a Profile for comparison.", 422)
        if profile is not None and artifact_type != "CV_SUGGESTIONS":
            snapshot["profile"] = {
                "headline": profile.headline,
                "competencies": profile.competencies,
                "domain_knowledge": profile.domain_knowledge,
                "technologies_tools": profile.technologies_tools,
                "languages": profile.languages,
                "credentials_licenses": profile.credentials_licenses,
                "education": profile.education,
                "experience": profile.experience,
                "eligibility_work_rights": profile.eligibility_work_rights,
            }
        return snapshot

    def _require_quota(self, user_id: str, plan: str, artifact_type: ArtifactType) -> None:
        now = datetime.now(UTC)
        if artifact_type == "CV_SUGGESTIONS":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            entitlement = CV_SUGGESTION_MONTHLY_LIMIT
            types = [artifact_type]
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            entitlement = PRIVATE_AI_DAILY_LIMIT
            types = list(JOB_REQUIRED)
        usage = (
            self.session.scalar(
                select(func.count())
                .select_from(PrivateAiArtifact)
                .where(
                    PrivateAiArtifact.user_id == user_id,
                    PrivateAiArtifact.artifact_type.in_(types),
                    PrivateAiArtifact.created_at >= start,
                )
            )
            or 0
        )
        EntitlementService(self.session).require_capacity(
            user_id=user_id,
            plan=plan,
            entitlement_key=entitlement,
            current_usage=usage,
        )


class ProfileSuggestionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, user_id: str) -> list[ProfileSuggestion]:
        return list(
            self.session.scalars(
                select(ProfileSuggestion)
                .where(ProfileSuggestion.user_id == user_id)
                .order_by(ProfileSuggestion.created_at.desc())
            )
        )

    def decide(
        self,
        suggestion_id: str,
        user_id: str,
        decision: Literal["ACCEPTED", "EDITED", "REJECTED"],
        edit: SuggestionEdit | None = None,
    ) -> ProfileSuggestion:
        suggestion = self.session.scalar(
            select(ProfileSuggestion).where(
                ProfileSuggestion.id == suggestion_id,
                ProfileSuggestion.user_id == user_id,
            )
        )
        if suggestion is None:
            raise NotFoundError()
        if suggestion.status != "PENDING":
            raise AppError(
                "SUGGESTION_ALREADY_DECIDED", "This suggestion was already decided.", 409
            )
        if decision == "EDITED" and edit is None:
            raise AppError("EDIT_REQUIRED", "Provide the edited suggestion.", 422)
        if decision != "REJECTED":
            value = dict(suggestion.suggestion)
            if edit is not None:
                value.update(edit.model_dump(exclude_none=True))
                suggestion.suggestion = value
            self._apply_to_profile(user_id, suggestion.category, value)
        suggestion.status = decision
        suggestion.decided_at = utcnow()
        self.session.commit()
        return suggestion

    def _apply_to_profile(self, user_id: str, category: str, value: dict[str, object]) -> None:
        profile = self.session.get(ProfessionalProfile, user_id)
        if profile is None:
            profile = ProfessionalProfile(user_id=user_id)
            self.session.add(profile)
            self.session.flush()
        display = str(value["display_name"]).strip()
        if category == "COMPETENCY":
            items = list(profile.competencies)
            item = {
                "canonical_id": value.get("canonical_id"),
                "display_name": display,
                "proficiency": value.get("proficiency"),
            }
            if not any(
                str(current.get("display_name", "")).casefold() == display.casefold()
                for current in items
            ):
                items.append(item)
            profile.competencies = items
        elif category == "DOMAIN_KNOWLEDGE":
            profile.domain_knowledge = self._append_unique(profile.domain_knowledge, display)
        elif category == "TECHNOLOGY":
            profile.technologies_tools = self._append_unique(profile.technologies_tools, display)
        elif category == "LANGUAGE":
            items = list(profile.languages)
            if not any(
                str(current.get("language", "")).casefold() == display.casefold()
                for current in items
            ):
                items.append({"language": display, "proficiency": value.get("proficiency")})
            profile.languages = items
        elif category == "CREDENTIAL":
            profile.credentials_licenses = self._append_unique(
                profile.credentials_licenses, display
            )
        else:
            raise AppError("SUGGESTION_CATEGORY_INVALID", "This suggestion cannot be applied.", 422)
        profile.updated_at = utcnow()

    @staticmethod
    def _append_unique(items: list[str], value: str) -> list[str]:
        result = list(items)
        if value.casefold() not in {item.casefold() for item in result}:
            result.append(value)
        return result
