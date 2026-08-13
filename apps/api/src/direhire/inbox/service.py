from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.contracts import JOB_ANALYSIS_PROMPT_VERSION, JOB_DEMAND_SCHEMA_VERSION
from direhire.errors import NotFoundError
from direhire.models import Job, JobDemandProfile, JobVersion, UserJob


class InboxService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, user_id: str) -> list[dict[str, object]]:
        rows = self.session.execute(
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
        items: list[dict[str, object]] = []
        seen: set[str] = set()
        for user_job, job, version, profile in rows:
            if user_job.id in seen:
                continue
            seen.add(user_job.id)
            items.append(self._read(user_job, job, version, profile))
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
        return self._read(user_job, job, version, profile)

    @staticmethod
    def _read(
        user_job: UserJob,
        job: Job,
        version: JobVersion | None,
        profile: JobDemandProfile | None,
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
        }
