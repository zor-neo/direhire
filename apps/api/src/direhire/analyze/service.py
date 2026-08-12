from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from direhire.ai.private_service import PrivateAiRequestService
from direhire.ai.service import queue_public_job_analysis
from direhire.entitlements.service import ANALYZE_JOB_MONTHLY_LIMIT, EntitlementService
from direhire.errors import AppError, NotFoundError
from direhire.jobs.service import CanonicalJobService
from direhire.models import (
    AdHocJobAnalysis,
    Job,
    JobDemandProfile,
    JobVersion,
    OutboxEvent,
    PrivateAiArtifact,
    UserJob,
    utcnow,
)
from direhire.operations.controls import PlatformControlService
from direhire.sources.adapters.generic_public import GenericPublicAdapter
from direhire.sources.validation import normalize_public_url
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService


class AnalyzeJobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def request_public(
        self, user_id: str, plan: str, url: str, correlation_id: str
    ) -> AdHocJobAnalysis:
        PlatformControlService(self.session).require(
            "PUBLIC_AI", "Public job analysis is temporarily unavailable."
        )
        normalized = normalize_public_url(url)
        key = self._key(user_id, "PUBLIC_URL", normalized)
        existing = self.session.scalar(
            select(AdHocJobAnalysis).where(AdHocJobAnalysis.idempotency_key == key)
        )
        if existing is not None:
            return existing
        self._require_quota(user_id, plan)
        version = self.session.scalar(
            select(JobVersion)
            .where(JobVersion.source_url == normalized)
            .order_by(JobVersion.captured_at.desc())
        )
        row = AdHocJobAnalysis(
            user_id=user_id,
            input_type="PUBLIC_URL",
            idempotency_key=key,
            normalized_url=normalized,
            status="QUEUED",
        )
        self.session.add(row)
        self.session.flush()
        if version is not None:
            demand = queue_public_job_analysis(self.session, version, correlation_id=correlation_id)
            row.job_id = version.job_id
            row.demand_profile_id = demand.id
            row.status = "ANALYSIS_QUEUED"
        else:
            self.session.add(
                OutboxEvent(
                    event_id=f"evt_{uuid.uuid4().hex}",
                    event_type="analyze.job.requested",
                    schema_version=1,
                    correlation_id=correlation_id,
                    payload={"analysis_id": row.id, "user_id": user_id},
                )
            )
        self.session.commit()
        return row

    def request_pasted(
        self, user_id: str, plan: str, text: str, correlation_id: str
    ) -> AdHocJobAnalysis:
        PlatformControlService(self.session).require(
            "PRIVATE_AI", "Private AI is temporarily unavailable."
        )
        normalized_text = "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()
        if len(normalized_text) < 100 or len(normalized_text) > 100_000:
            raise AppError(
                "JOB_TEXT_INVALID",
                "Paste a job description between 100 and 100,000 characters.",
                422,
            )
        digest = hashlib.sha256(normalized_text.encode()).hexdigest()
        key = self._key(user_id, "PASTED_TEXT", digest)
        existing = self.session.scalar(
            select(AdHocJobAnalysis).where(AdHocJobAnalysis.idempotency_key == key)
        )
        if existing is not None:
            return existing
        self._require_quota(user_id, plan)
        artifact = PrivateAiArtifact(
            user_id=user_id,
            artifact_type="PASTED_JOB_ANALYSIS",
            idempotency_key=f"private-ai:{key}",
            status="QUEUED",
            input_hash=digest,
            input_snapshot={"job_description": normalized_text},
        )
        self.session.add(artifact)
        self.session.flush()
        row = AdHocJobAnalysis(
            user_id=user_id,
            input_type="PASTED_TEXT",
            idempotency_key=key,
            private_text=normalized_text,
            private_artifact_id=artifact.id,
            status="ANALYSIS_QUEUED",
        )
        self.session.add(row)
        self.session.add(
            OutboxEvent(
                event_id=f"evt_{uuid.uuid4().hex}",
                event_type="private.ai.requested",
                schema_version=1,
                correlation_id=correlation_id,
                payload={
                    "artifact_id": artifact.id,
                    "user_id": user_id,
                    "artifact_type": "PASTED_JOB_ANALYSIS",
                },
            )
        )
        self.session.commit()
        return row

    def list(self, user_id: str) -> list[dict[str, object]]:
        return [
            self.read_model(item)
            for item in self.session.scalars(
                select(AdHocJobAnalysis)
                .where(AdHocJobAnalysis.user_id == user_id)
                .order_by(AdHocJobAnalysis.created_at.desc())
            )
        ]

    def get(self, analysis_id: str, user_id: str) -> dict[str, object]:
        return self.read_model(self._owned(analysis_id, user_id))

    def save(self, analysis_id: str, user_id: str) -> dict[str, object]:
        row = self._owned(analysis_id, user_id)
        if self._content(row) is None:
            raise AppError("ANALYSIS_NOT_READY", "The analysis is not ready to save.", 409)
        if row.job_id is not None:
            existing = self.session.scalar(
                select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == row.job_id)
            )
            if existing is None:
                self.session.add(UserJob(user_id=user_id, job_id=row.job_id, status="SAVED"))
        row.saved_at = utcnow()
        row.updated_at = utcnow()
        self.session.commit()
        return self.read_model(row)

    def delete(self, analysis_id: str, user_id: str) -> None:
        row = self._owned(analysis_id, user_id)
        if row.private_artifact_id:
            PrivateAiRequestService(self.session).delete(row.private_artifact_id, user_id)
            return
        self.session.delete(row)
        self.session.commit()

    def create_watch(self, analysis_id: str, user_id: str) -> object:
        row = self._owned(analysis_id, user_id)
        content = self._content(row)
        if content is None:
            raise AppError("ANALYSIS_NOT_READY", "The analysis is not ready.", 409)
        target = str(
            content.get("normalized_occupation") or content.get("role_family") or ""
        ).strip()
        if not target:
            raise AppError(
                "WATCH_DRAFT_UNAVAILABLE",
                "The analysis does not contain a reliable occupation target.",
                409,
            )
        return WatchService(self.session).create(
            user_id,
            WatchCreate(
                name=f"{target} opportunities"[:120],
                target_terms=[target],
                raw_intent=f"Draft created explicitly from Analyze-a-Job result {row.id}",
            ),
        )

    def read_model(self, row: AdHocJobAnalysis) -> dict[str, object]:
        content = self._content(row)
        status, error = self._derived_status(row)
        return {
            "id": row.id,
            "input_type": row.input_type,
            "normalized_url": row.normalized_url,
            "job_id": row.job_id,
            "status": status,
            "analysis": content,
            "similar_openings": self._similar(row, content) if content else [],
            "saved": row.saved_at is not None,
            "error_code": error,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _owned(self, analysis_id: str, user_id: str) -> AdHocJobAnalysis:
        row = self.session.scalar(
            select(AdHocJobAnalysis).where(
                AdHocJobAnalysis.id == analysis_id,
                AdHocJobAnalysis.user_id == user_id,
            )
        )
        if row is None:
            raise NotFoundError()
        return row

    def _content(self, row: AdHocJobAnalysis) -> dict[str, object] | None:
        if row.demand_profile_id:
            demand = self.session.get(JobDemandProfile, row.demand_profile_id)
            if demand is not None and demand.status == "SUCCEEDED" and demand.profile:
                value = demand.profile.get("content", demand.profile)
                return value if isinstance(value, dict) else None
        if row.private_artifact_id:
            artifact = self.session.get(PrivateAiArtifact, row.private_artifact_id)
            if artifact is not None and artifact.status == "SUCCEEDED":
                return artifact.content
        return None

    def _derived_status(self, row: AdHocJobAnalysis) -> tuple[str, str | None]:
        if row.demand_profile_id:
            demand = self.session.get(JobDemandProfile, row.demand_profile_id)
            if demand is not None:
                return demand.status, demand.error_code
        if row.private_artifact_id:
            artifact = self.session.get(PrivateAiArtifact, row.private_artifact_id)
            if artifact is not None:
                return artifact.status, artifact.error_code
        return row.status, row.error_code

    def _similar(
        self, row: AdHocJobAnalysis, content: dict[str, object]
    ) -> list[dict[str, object]]:
        occupation = content.get("normalized_occupation") or content.get("role_family")
        if not occupation:
            return []
        results: list[dict[str, object]] = []
        candidates = self.session.execute(
            select(JobDemandProfile, JobVersion, Job)
            .join(JobVersion, JobVersion.id == JobDemandProfile.job_version_id)
            .join(Job, Job.id == JobVersion.job_id)
            .where(JobDemandProfile.status == "SUCCEEDED")
            .order_by(JobVersion.captured_at.desc())
            .limit(100)
        )
        for demand, version, job in candidates:
            if job.id == row.job_id or not demand.profile:
                continue
            candidate = demand.profile.get("content", demand.profile)
            if not isinstance(candidate, dict):
                continue
            candidate_occupation = candidate.get("normalized_occupation") or candidate.get(
                "role_family"
            )
            if str(candidate_occupation).casefold() != str(occupation).casefold():
                continue
            results.append(
                {
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location_raw,
                    "source_url": version.source_url,
                }
            )
            if len(results) == 5:
                break
        return results

    def _require_quota(self, user_id: str, plan: str) -> None:
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = (
            self.session.scalar(
                select(func.count())
                .select_from(AdHocJobAnalysis)
                .where(
                    AdHocJobAnalysis.user_id == user_id,
                    AdHocJobAnalysis.created_at >= start,
                )
            )
            or 0
        )
        EntitlementService(self.session).require_capacity(
            user_id=user_id,
            plan=plan,
            entitlement_key=ANALYZE_JOB_MONTHLY_LIMIT,
            current_usage=usage,
        )

    @staticmethod
    def _key(user_id: str, input_type: str, value: str) -> str:
        digest = hashlib.sha256(value.encode()).hexdigest()
        return f"analyze:{user_id}:{input_type}:{digest}"


class PublicAnalyzeJobProcessor:
    def __init__(self, session: Session, fetch: Callable[[str], str]) -> None:
        self.session = session
        self.fetch = fetch

    def process(self, analysis_id: str, correlation_id: str) -> AdHocJobAnalysis:
        row = self.session.get(AdHocJobAnalysis, analysis_id)
        if row is None:
            raise AppError("ANALYSIS_NOT_FOUND", "The analysis request was not found.", 404)
        if row.demand_profile_id is not None or row.status == "PERMANENT_FAILED":
            return row
        if row.input_type != "PUBLIC_URL" or not row.normalized_url:
            raise AppError("ANALYSIS_INPUT_INVALID", "The analysis input is invalid.", 422)
        row.status = "FETCHING"
        self.session.commit()
        try:
            html = self.fetch(row.normalized_url)
            candidates = GenericPublicAdapter().discover_jobs(html)
            exact = [
                candidate
                for candidate in candidates
                if normalize_public_url(candidate.url) == row.normalized_url
            ]
            selected = exact[0] if exact else candidates[0] if len(candidates) == 1 else None
            if selected is None:
                raise AppError(
                    "JOB_PAGE_UNSUPPORTED",
                    "No unambiguous public JobPosting was found at this URL.",
                    422,
                )
            selected = replace(selected, url=row.normalized_url)
            job, version = CanonicalJobService(self.session).upsert("generic_public", selected)
            demand = queue_public_job_analysis(self.session, version, correlation_id=correlation_id)
            row.job_id = job.id
            row.demand_profile_id = demand.id
            row.status = "ANALYSIS_QUEUED"
            row.error_code = None
            row.updated_at = utcnow()
            self.session.commit()
            return row
        except AppError as exc:
            row = self.session.get(AdHocJobAnalysis, analysis_id)
            if row is not None:
                row.status = "RETRYABLE_FAILED" if exc.retryable else "PERMANENT_FAILED"
                row.error_code = exc.code
                row.updated_at = utcnow()
                self.session.commit()
            if exc.retryable:
                raise
            return row
