import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.models import Job, JobVersion, SourceListing, utcnow
from direhire.sources.contracts import DiscoveredJob


class CanonicalJobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, adapter_key: str, candidate: DiscoveredJob) -> tuple[Job, JobVersion]:
        listing = self.session.scalar(
            select(SourceListing).where(
                SourceListing.adapter_key == adapter_key,
                SourceListing.external_id == candidate.external_id,
            )
        )
        if listing is not None:
            job = self.session.get(Job, listing.job_id)
            if job is None:
                raise RuntimeError("source listing references a missing job")
            listing.last_seen_at = utcnow()
        else:
            identity = self._hash(
                "|".join(
                    (
                        candidate.company.casefold().strip(),
                        candidate.title.casefold().strip(),
                        candidate.location_raw.casefold().strip(),
                    )
                )
            )
            job = self.session.scalar(select(Job).where(Job.identity_key == identity))
            if job is None:
                job = Job(
                    identity_key=identity,
                    title=candidate.title,
                    company=candidate.company,
                    location_raw=candidate.location_raw,
                )
                self.session.add(job)
                self.session.flush()
            self.session.add(
                SourceListing(
                    adapter_key=adapter_key,
                    external_id=candidate.external_id,
                    job_id=job.id,
                    url=candidate.url,
                )
            )
        content_hash = self._hash(candidate.description)
        version = self.session.scalar(
            select(JobVersion).where(
                JobVersion.job_id == job.id,
                JobVersion.content_hash == content_hash,
            )
        )
        if version is None:
            version = JobVersion(
                job_id=job.id,
                content_hash=content_hash,
                description=candidate.description,
                source_url=candidate.url,
            )
            self.session.add(version)
            self.session.flush()
        return job, version

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()
