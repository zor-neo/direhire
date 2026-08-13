import json

from direhire.ai.private_orchestrator import PrivateAiOrchestrator
from direhire.ai.providers import ProviderResponse, ProviderUsage
from direhire.analyze.service import AnalyzeJobService, PublicAnalyzeJobProcessor
from direhire.models import (
    AdHocJobAnalysis,
    AiModelPolicy,
    Job,
    JobDemandProfile,
    JobWatch,
    NotificationDigest,
    OutboxEvent,
    PrivateAiArtifact,
    User,
    UserJob,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A
from tests.integration.test_public_ai_orchestrator import valid_content


class PrivateProvider:
    def generate(self, **kwargs: object) -> ProviderResponse:
        return ProviderResponse(
            valid_content(),
            "OPENROUTER",
            "anthropic",
            str(kwargs["model"]),
            ProviderUsage(80, 40, 120),
        )


def seed_user(session: Session) -> None:
    session.add(
        User(
            id=str(USER_A),
            cognito_subject="analyze-user",
            email="analyze@example.invalid",
        )
    )
    session.add(
        AiModelPolicy(
            provider="OPENROUTER",
            capability="AI_STANDARD",
            model="approved/private-model",
            max_output_tokens=4096,
            input_cost_microusd_per_million=1000,
            output_cost_microusd_per_million=2000,
        )
    )
    session.commit()


def test_pasted_job_stays_private_and_creates_only_explicit_draft_watch(
    session_factory: sessionmaker[Session],
) -> None:
    pasted = (
        "Fictional Labs seeks a Backend Engineer to build Python APIs and PostgreSQL services. "
        "The role is full-time and remote only within Thailand. Applicants should operate reliable "
        "production systems and communicate clearly with product teams."
    )
    with session_factory() as database:
        seed_user(database)
        service = AnalyzeJobService(database)
        row = service.request_pasted(str(USER_A), "FREE", pasted, "p" * 36)
        repeated = service.request_pasted(str(USER_A), "FREE", pasted, "q" * 36)
        event = database.scalar(select(OutboxEvent))

        assert repeated.id == row.id
        assert database.scalar(select(func.count()).select_from(Job)) == 0
        assert event is not None and pasted not in json.dumps(event.payload)
        artifact = database.get(PrivateAiArtifact, row.private_artifact_id)
        assert artifact is not None and artifact.input_snapshot["job_description"] == pasted

        PrivateAiOrchestrator(database, PrivateProvider()).process(
            artifact.id, correlation_id="p" * 36
        )
        result = service.get(row.id, str(USER_A))
        assert (
            result["analysis"]["role_reality"]["primary_occupation"]  # type: ignore[index]
            == "Backend Engineer"
        )
        assert database.scalar(select(func.count()).select_from(NotificationDigest)) == 0
        assert database.scalar(select(func.count()).select_from(JobWatch)) == 0

        saved = service.save(row.id, str(USER_A))
        assert saved["saved"] is True
        draft = service.create_watch(row.id, str(USER_A))
        assert draft.status == "DRAFT"
        assert draft.target_terms == ["Backend Engineer"]


def test_public_url_is_fetched_into_shared_corpus_and_reuses_structured_analysis(
    session_factory: sessionmaker[Session],
) -> None:
    url = "https://jobs.example.invalid/job/42"
    html = f"""
    <script type="application/ld+json">
    {{
      "@type": "JobPosting",
      "identifier": {{"value": "job-42"}},
      "url": "{url}",
      "title": "Backend Engineer",
      "hiringOrganization": {{"name": "Fictional Labs"}},
      "jobLocation": {{"address": {{"addressLocality": "Bangkok", "addressCountry": "TH"}}}},
      "description": "Build Python APIs and PostgreSQL services for a fictional product."
    }}
    </script>
    """
    with session_factory() as database:
        seed_user(database)
        service = AnalyzeJobService(database)
        row = service.request_public(str(USER_A), "FREE", url, "u" * 36)
        completed = PublicAnalyzeJobProcessor(database, lambda requested: html).process(
            row.id, "u" * 36
        )
        demand = database.get(JobDemandProfile, completed.demand_profile_id)
        assert demand is not None
        demand.status = "SUCCEEDED"
        demand.profile = {"content": json.loads(valid_content())}
        database.commit()

        result = service.get(row.id, str(USER_A))
        assert result["status"] == "SUCCEEDED"
        assert database.scalar(select(func.count()).select_from(Job)) == 1
        assert database.scalar(select(func.count()).select_from(JobDemandProfile)) == 1
        service.save(row.id, str(USER_A))
        assert database.scalar(select(func.count()).select_from(UserJob)) == 1

        repeated = service.request_public(str(USER_A), "FREE", url, "v" * 36)
        assert repeated.id == row.id
        assert database.scalar(select(func.count()).select_from(AdHocJobAnalysis)) == 1


def test_failed_analysis_is_overridden_on_re_request_and_purged_on_delete(
    session_factory: sessionmaker[Session],
) -> None:
    url = "https://jobs.example.invalid/job/failed-1"
    with session_factory() as database:
        seed_user(database)
        service = AnalyzeJobService(database)
        row = service.request_public(str(USER_A), "FREE", url, "f" * 36)
        row.status = "PERMANENT_FAILED"
        row.error_code = "JOB_PAGE_UNSUPPORTED"
        database.commit()

        # Re-requesting the failed URL overrides the failed state and re-queues it
        retried = service.request_public(str(USER_A), "FREE", url, "r" * 36)
        assert retried.id == row.id
        assert retried.status == "QUEUED"
        assert retried.error_code is None

        # Purging/deleting the analysis removes it from storage
        service.delete(row.id, str(USER_A))
        assert database.scalar(select(func.count()).select_from(AdHocJobAnalysis)) == 0

