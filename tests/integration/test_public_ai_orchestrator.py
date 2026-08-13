import json

import pytest
from direhire.ai.contracts import JobDemandProfileContent
from direhire.ai.orchestrator import AiOrchestrator
from direhire.ai.providers import ProviderResponse, ProviderUsage
from direhire.ai.service import queue_public_job_analysis
from direhire.errors import AppError
from direhire.models import AiModelPolicy, AiOperation, Job, JobVersion
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker


class FakeProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def generate(self, **kwargs: object) -> ProviderResponse:
        del kwargs
        text = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return ProviderResponse(
            text=text,
            provider="GEMINI",
            route_key="project-a",
            model="test-model",
            usage=ProviderUsage(prompt_tokens=100, output_tokens=50, total_tokens=150),
        )


def valid_content() -> str:
    content = JobDemandProfileContent(
        role_summary="Build and operate backend services.",
        role_reality={
            "headline": "Backend Engineer building Python APIs",
            "primary_archetype": "BACKEND_DEVELOPER",
            "primary_occupation": "Backend Engineer",
            "secondary_occupations": [],
            "title_alignment": "ACCURATE",
            "primary_mission": "Build robust Python REST APIs",
            "breadth": "SPECIALIZED",
        },
        seniority={
            "assessment": "MID",
            "explicit_min_years": 3.0,
            "explicit_max_years": 5.0,
            "interpretation_confidence": "HIGH",
            "reason": "Requires 3-5 years Python experience",
        },
        demand_clusters=[
            {
                "name": "Python API Development",
                "priority": "CORE",
                "reason": "Core job duty",
                "evidence": "Build Python APIs",
                "evidence_strength": "EXPLICIT",
            }
        ],
        competencies=[
            {
                "canonical_id": "python",
                "display_name": "Python",
                "category": "TECHNICAL",
                "priority": "CORE",
                "evidence": "Strong Python required",
                "evidence_strength": "EXPLICIT",
            }
        ],
        responsibility_clusters=[
            {
                "value": "API Development",
                "evidence": "Build Python APIs",
                "evidence_strength": "EXPLICIT",
                "interpretation_confidence": "HIGH",
            }
        ],
        requirements=[
            {
                "category": "CAPABILITY",
                "title": "Python REST API development",
                "evidence": "Build Python APIs",
                "evidence_strength": "EXPLICIT",
            }
        ],
        job_constraints=[],
        work_location_summary={
            "value": "Thailand",
            "evidence": "Thailand",
            "evidence_strength": "EXPLICIT",
            "interpretation_confidence": "HIGH",
        },
        work_arrangement_summary={
            "value": "Remote",
            "evidence": "Remote within Thailand",
            "evidence_strength": "EXPLICIT",
            "interpretation_confidence": "HIGH",
        },
        remote_eligibility="LOCATION_RESTRICTED",
        real_work_scenarios=["Operate production APIs"],
        contradictions=[],
        overall_confidence="HIGH",
    )
    return content.model_dump_json()


def seed_analysis(database: Session) -> str:
    job = Job(
        identity_key="a" * 64,
        title="Backend Engineer",
        company="Fictional Labs",
        location_raw="Thailand",
    )
    database.add(job)
    database.flush()
    version = JobVersion(
        job_id=job.id,
        content_hash="b" * 64,
        description="<p>Build Python APIs. Contact hiring@example.invalid.</p>",
        source_url="https://jobs.example.invalid/1",
    )
    database.add(version)
    database.flush()
    profile = queue_public_job_analysis(database, version, correlation_id="c" * 36)
    database.add(
        AiModelPolicy(
            provider="GEMINI",
            capability="AI_STANDARD",
            model="test-model",
            max_output_tokens=4096,
            input_cost_microusd_per_million=1_500_000,
            output_cost_microusd_per_million=7_500_000,
        )
    )
    database.commit()
    return profile.id


def test_structured_analysis_is_validated_metered_and_idempotently_reused(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        profile_id = seed_analysis(database)
        provider = FakeProvider([valid_content()])
        orchestrator = AiOrchestrator(database, provider)
        completed = orchestrator.analyze_public_job(profile_id, correlation_id="c" * 36)
        repeated = orchestrator.analyze_public_job(profile_id, correlation_id="c" * 36)

        assert completed.status == "SUCCEEDED"
        assert repeated.profile == completed.profile
        assert provider.calls == 1
        assert completed.profile is not None
        assert completed.profile["provenance"]["route_key"] == "project-a"
        operation = database.scalar(select(AiOperation))
        assert operation is not None
        assert operation.prompt_tokens == 100
        assert operation.output_tokens == 50
        assert operation.estimated_cost_microusd == 525
        assert database.scalar(select(func.count()).select_from(AiOperation)) == 1
        assert "hiring@example.invalid" not in json.dumps(completed.profile)


def test_malformed_ai_output_gets_one_bounded_repair_then_degrades(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        profile_id = seed_analysis(database)
        provider = FakeProvider(["{}", '{"still":"invalid"}'])
        completed = AiOrchestrator(database, provider).analyze_public_job(
            profile_id, correlation_id="c" * 36
        )

        assert completed.status == "DEGRADED_FAILED"
        assert completed.error_code == "AI_OUTPUT_INVALID"
        assert provider.calls == 2
        operation = database.scalar(select(AiOperation))
        assert operation is not None
        assert operation.provider_attempts == 2
        assert operation.estimated_cost_microusd == 1050


def test_private_data_can_never_use_public_route() -> None:
    with pytest.raises(AppError) as error:
        AiOrchestrator.require_public_route("SENSITIVE_PRIVATE_DATA")
    assert error.value.code == "AI_PRIVATE_ROUTE_UNAVAILABLE"
