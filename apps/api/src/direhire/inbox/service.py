from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.contracts import JOB_ANALYSIS_PROMPT_VERSION, JOB_DEMAND_SCHEMA_VERSION
from direhire.errors import NotFoundError
from direhire.models import Job, JobDemandProfile, JobVersion, JobWatch, UserJob, WatchMatch


class InboxService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, user_id: str, *, watch_id: str | None = None) -> list[dict[str, object]]:
        # Fetch watch matches for this user
        watch_matches_query = (
            select(WatchMatch.job_id, JobWatch.id, JobWatch.name)
            .join(JobWatch, JobWatch.id == WatchMatch.watch_id)
            .where(JobWatch.owner_id == user_id)
        )
        if watch_id:
            watch_matches_query = watch_matches_query.where(JobWatch.id == watch_id)
        watch_matches = self.session.execute(watch_matches_query).all()

        job_to_watches: dict[str, list[dict[str, str]]] = {}
        for j_id, w_id, w_name in watch_matches:
            job_to_watches.setdefault(j_id, []).append({"id": w_id, "name": w_name})

        query = (
            select(UserJob, Job, JobVersion, JobDemandProfile)
            .join(Job, Job.id == UserJob.job_id)
            .outerjoin(JobVersion, JobVersion.job_id == Job.id)
            .outerjoin(
                JobDemandProfile,
                (JobDemandProfile.job_version_id == JobVersion.id)
                & (JobDemandProfile.schema_version == JOB_DEMAND_SCHEMA_VERSION)
                & (JobDemandProfile.prompt_version == JOB_ANALYSIS_PROMPT_VERSION),
            )
            .where(UserJob.user_id == user_id)
            .order_by(UserJob.created_at.desc(), JobVersion.captured_at.desc())
        )
        if watch_id:
            matching_job_ids = list(job_to_watches.keys())
            if not matching_job_ids:
                return []
            query = query.where(Job.id.in_(matching_job_ids))

        rows = self.session.execute(query)
        items: list[dict[str, object]] = []
        seen: set[str] = set()
        for user_job, job, version, profile in rows:
            if user_job.id in seen:
                continue
            seen.add(user_job.id)
            items.append(
                self._read(user_job, job, version, profile, job_to_watches.get(job.id, []))
            )
        return items

    def set_status(self, user_job_id: str, user_id: str, status: str) -> dict[str, object]:
        row = self.session.execute(
            select(UserJob, Job, JobVersion)
            .join(Job, Job.id == UserJob.job_id)
            .outerjoin(JobVersion, JobVersion.job_id == Job.id)
            .where(UserJob.id == user_job_id, UserJob.user_id == user_id)
            .order_by(JobVersion.captured_at.desc())
            .limit(1)
        ).one_or_none()
        if row is None:
            raise NotFoundError()
        user_job, job, version = row
        user_job.status = status
        self.session.commit()
        profile = self.session.scalar(
            select(JobDemandProfile)
            .join(JobVersion, JobVersion.id == JobDemandProfile.job_version_id)
            .where(
                JobVersion.job_id == job.id,
                JobDemandProfile.schema_version == JOB_DEMAND_SCHEMA_VERSION,
                JobDemandProfile.prompt_version == JOB_ANALYSIS_PROMPT_VERSION,
            )
            .order_by(JobVersion.captured_at.desc())
        )
        watch_matches = self.session.execute(
            select(WatchMatch.job_id, JobWatch.id, JobWatch.name)
            .join(JobWatch, JobWatch.id == WatchMatch.watch_id)
            .where(JobWatch.owner_id == user_id, WatchMatch.job_id == job.id)
        ).all()
        matched_watches = [{"id": w_id, "name": w_name} for _, w_id, w_name in watch_matches]
        return self._read(user_job, job, version, profile, matched_watches)

    def retry_analysis(self, user_job_id: str, user_id: str) -> dict[str, object]:
        import uuid

        from direhire.ai.service import retry_public_job_analysis
        from direhire.errors import AppError

        row = self.session.execute(
            select(UserJob, Job, JobVersion)
            .join(Job, Job.id == UserJob.job_id)
            .outerjoin(JobVersion, JobVersion.job_id == Job.id)
            .where(UserJob.id == user_job_id, UserJob.user_id == user_id)
            .order_by(JobVersion.captured_at.desc())
            .limit(1)
        ).one_or_none()
        if row is None:
            raise NotFoundError()
        user_job, job, version = row
        if version is None:
            raise AppError("JOB_VERSION_NOT_FOUND", "No job content available to analyze.", 404)

        profile = retry_public_job_analysis(self.session, version, correlation_id=str(uuid.uuid4()))
        self.session.commit()

        watch_matches = self.session.execute(
            select(WatchMatch.job_id, JobWatch.id, JobWatch.name)
            .join(JobWatch, JobWatch.id == WatchMatch.watch_id)
            .where(JobWatch.owner_id == user_id, WatchMatch.job_id == job.id)
        ).all()
        matched_watches = [{"id": w_id, "name": w_name} for _, w_id, w_name in watch_matches]
        return self._read(user_job, job, version, profile, matched_watches)

    @staticmethod
    def _read(
        user_job: UserJob,
        job: Job,
        version: JobVersion | None,
        profile: JobDemandProfile | None,
        matched_watches: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        return {
            "id": user_job.id,
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location_raw,
            "source_url": version.source_url if version is not None else None,
            "job_lifecycle": job.lifecycle_status,
            "status": user_job.status,
            "created_at": user_job.created_at,
            "analysis_status": profile.status if profile is not None else "NOT_REQUESTED",
            "analysis": profile.profile if profile is not None else None,
            "matched_watches": matched_watches or [],
        }
