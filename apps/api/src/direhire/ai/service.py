import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.contracts import JOB_ANALYSIS_PROMPT_VERSION, JOB_DEMAND_SCHEMA_VERSION
from direhire.models import JobDemandProfile, JobVersion, OutboxEvent


def queue_public_job_analysis(
    session: Session, job_version: JobVersion, *, correlation_id: str
) -> JobDemandProfile:
    profile = session.scalar(
        select(JobDemandProfile).where(
            JobDemandProfile.job_version_id == job_version.id,
            JobDemandProfile.schema_version == JOB_DEMAND_SCHEMA_VERSION,
            JobDemandProfile.prompt_version == JOB_ANALYSIS_PROMPT_VERSION,
        )
    )
    if profile is not None:
        return profile
    profile = JobDemandProfile(
        job_version_id=job_version.id,
        schema_version=JOB_DEMAND_SCHEMA_VERSION,
        prompt_version=JOB_ANALYSIS_PROMPT_VERSION,
        input_hash=job_version.content_hash,
    )
    session.add(profile)
    session.flush()
    session.add(
        OutboxEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            event_type="job.analysis.requested",
            schema_version=1,
            correlation_id=correlation_id,
            payload={"profile_id": profile.id, "job_version_id": job_version.id},
        )
    )
    return profile
