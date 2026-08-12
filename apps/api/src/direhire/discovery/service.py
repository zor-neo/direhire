from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.service import queue_public_job_analysis
from direhire.config import get_settings
from direhire.errors import AppError
from direhire.jobs.service import CanonicalJobService
from direhire.models import (
    Job,
    JobVersion,
    JobWatch,
    JobWatchRun,
    SourceFetch,
    UserJob,
    WatchMatch,
    WatchSource,
    utcnow,
)
from direhire.notifications.service import queue_run_digest
from direhire.sources.adapters.ashby import AshbyAdapter
from direhire.sources.adapters.generic_public import GenericPublicAdapter
from direhire.sources.adapters.greenhouse import GreenhouseAdapter
from direhire.sources.adapters.lever import LeverAdapter
from direhire.sources.adapters.personio import PersonioAdapter
from direhire.sources.adapters.pinpoint import PinpointAdapter
from direhire.sources.adapters.recruitee import RecruiteeAdapter
from direhire.sources.adapters.synthetic_board import SyntheticBoardAdapter
from direhire.sources.coalescing import SharedFetchPending, SourceFetchCoalescer
from direhire.sources.contracts import SourceAdapter
from direhire.sources.policy_service import SourcePolicyService
from direhire.watches.matching import deterministic_match

ContentProvider = Callable[[WatchSource], str]


class DiscoveryProcessor:
    def __init__(self, session: Session, content_provider: ContentProvider) -> None:
        self.session = session
        self.content_provider = content_provider
        self.adapters: dict[str, SourceAdapter] = {
            SyntheticBoardAdapter.key: SyntheticBoardAdapter(),
            GenericPublicAdapter.key: GenericPublicAdapter(),
            GreenhouseAdapter.key: GreenhouseAdapter(),
            LeverAdapter.key: LeverAdapter(),
            AshbyAdapter.key: AshbyAdapter(),
            RecruiteeAdapter.key: RecruiteeAdapter(),
            PersonioAdapter.key: PersonioAdapter(),
            PinpointAdapter.key: PinpointAdapter(),
        }

    def process(self, run_id: str) -> JobWatchRun:
        run = self.session.get(JobWatchRun, run_id)
        if run is None:
            raise AppError("WORKFLOW_NOT_FOUND", "The discovery run was not found.", 404)
        if run.status == "SUCCEEDED":
            return run
        watch = self.session.get(JobWatch, run.watch_id)
        if watch is None:
            raise AppError("WORKFLOW_CANCELLED", "The Watch no longer exists.", 409)
        run.status = "RUNNING"
        self.session.commit()

        for source in watch.sources:
            if self._already_processed(run.id, source.id):
                continue
            unavailable_code = SourcePolicyService(self.session).unavailable_code(
                source.adapter_key
            )
            if unavailable_code is not None:
                run.sources_failed += 1
                self.session.add(
                    SourceFetch(
                        run_id=run.id,
                        watch_source_id=source.id,
                        status="SKIPPED",
                        warning_code=unavailable_code,
                    )
                )
                self.session.commit()
                continue
            try:
                count, matches = self._process_source(run, watch, source)
                SourcePolicyService(self.session).record_success(source.adapter_key)
                run.sources_succeeded += 1
                run.discovered_count += count
                run.matched_count += matches
                self.session.add(
                    SourceFetch(
                        run_id=run.id,
                        watch_source_id=source.id,
                        status="SUCCEEDED",
                        discovered_count=count,
                    )
                )
            except SharedFetchPending:
                self.session.rollback()
                run = self.session.get(JobWatchRun, run_id)
                if run is not None:
                    run.status = "QUEUED"
                    self.session.commit()
                raise
            except Exception as exc:
                self.session.rollback()
                run = self.session.get(JobWatchRun, run_id)
                if run is None:
                    raise
                SourcePolicyService(self.session).record_failure(source.adapter_key)
                run.sources_failed += 1
                self.session.add(
                    SourceFetch(
                        run_id=run.id,
                        watch_source_id=source.id,
                        status="PERMANENT_FAILED",
                        warning_code=(
                            exc.code if isinstance(exc, AppError) else "SOURCE_UNAVAILABLE"
                        ),
                    )
                )
            self.session.commit()

        run = self.session.get(JobWatchRun, run_id)
        if run is None:
            raise AppError("WORKFLOW_NOT_FOUND", "The discovery run was not found.", 404)
        run.status = "SUCCEEDED" if run.sources_succeeded else "PERMANENT_FAILED"
        if run.sources_succeeded and run.sources_failed:
            run.outcome = "COMPLETED_WITH_WARNINGS"
        elif run.sources_succeeded:
            run.outcome = "COMPLETED"
        else:
            run.outcome = "FAILED"
        run.active_marker = None
        run.completed_at = utcnow()
        queue_run_digest(self.session, run, watch_name=watch.name)
        self.session.commit()
        return run

    def _process_source(
        self, run: JobWatchRun, watch: JobWatch, source: WatchSource
    ) -> tuple[int, int]:
        adapter = self.adapters.get(source.adapter_key)
        if adapter is None:
            raise AppError("SOURCE_UNSUPPORTED", "This source is not supported.", 422)
        adapter.validate_source(source.url)
        discovered = SourceFetchCoalescer(self.session, get_settings()).discover(
            run_id=run.id,
            source=source,
            adapter=adapter,
            content_provider=self.content_provider,
        )
        matched = 0
        for candidate in discovered:
            job, version = CanonicalJobService(self.session).upsert(adapter.key, candidate)
            text = " ".join(
                (candidate.title, candidate.company, candidate.location_raw, candidate.description)
            )
            result = deterministic_match(
                text=text,
                target_terms=watch.target_terms,
                required_terms=watch.required_terms,
                excluded_terms=watch.excluded_terms,
            )
            if result.matched:
                self._record_match(run, watch, job, version, result)
                matched += 1
        return len(discovered), matched

    def _record_match(
        self,
        run: JobWatchRun,
        watch: JobWatch,
        job: Job,
        version: JobVersion,
        result: object,
    ) -> None:
        existing = self.session.scalar(
            select(WatchMatch).where(
                WatchMatch.run_id == run.id,
                WatchMatch.watch_id == watch.id,
                WatchMatch.job_id == job.id,
            )
        )
        if existing is None:
            self.session.add(
                WatchMatch(
                    run_id=run.id,
                    watch_id=watch.id,
                    job_id=job.id,
                    evidence={"match_type": "DETERMINISTIC_WATCH"},
                )
            )
        user_job = self.session.scalar(
            select(UserJob).where(UserJob.user_id == run.owner_id, UserJob.job_id == job.id)
        )
        if user_job is None:
            self.session.add(UserJob(user_id=run.owner_id, job_id=job.id))
        queue_public_job_analysis(self.session, version, correlation_id=run.correlation_id)

    def _already_processed(self, run_id: str, source_id: str) -> bool:
        return (
            self.session.scalar(
                select(SourceFetch.id).where(
                    SourceFetch.run_id == run_id, SourceFetch.watch_source_id == source_id
                )
            )
            is not None
        )
