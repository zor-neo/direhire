import json

from direhire.ai.private_orchestrator import PrivateAiOrchestrator
from direhire.ai.private_service import PrivateAiRequestService, ProfileSuggestionService
from direhire.ai.providers import ProviderResponse, ProviderUsage
from direhire.models import (
    AiModelPolicy,
    AiOperation,
    BaseCv,
    Job,
    JobDemandProfile,
    JobVersion,
    OutboxEvent,
    PrivateFile,
    ProfessionalProfile,
    ProfileSuggestion,
    User,
    UserJob,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


class StaticProvider:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body
        self.prompts: list[str] = []

    def generate(self, **kwargs: object) -> ProviderResponse:
        self.prompts.append(str(kwargs["prompt"]))
        return ProviderResponse(
            json.dumps(self.body),
            "OPENROUTER",
            "anthropic",
            str(kwargs["model"]),
            ProviderUsage(100, 50, 150),
        )


def seed_private_context(session: Session) -> tuple[str, str]:
    user_id = str(USER_A)
    session.add(
        User(
            id=user_id,
            cognito_subject="private-ai-user",
            email="private-ai@example.invalid",
            plan="PREMIUM",
        )
    )
    job = Job(
        identity_key="private-ai-job",
        title="Backend Engineer",
        company="Fictional Labs",
        location_raw="Remote in Thailand",
    )
    session.add(job)
    session.flush()
    version = JobVersion(
        job_id=job.id,
        content_hash="a" * 64,
        description="Build Python services with PostgreSQL.",
        source_url="https://jobs.example.invalid/backend",
    )
    session.add(version)
    session.flush()
    session.add_all(
        [
            UserJob(user_id=user_id, job_id=job.id),
            JobDemandProfile(
                job_version_id=version.id,
                schema_version=1,
                prompt_version="jd-holistic-v1",
                input_hash="b" * 64,
                status="SUCCEEDED",
                profile={"content": {"summary": "Python and PostgreSQL are required."}},
            ),
            ProfessionalProfile(
                user_id=user_id,
                headline="Backend engineer",
                competencies=[{"display_name": "Python", "proficiency": 4}],
            ),
            AiModelPolicy(
                provider="OPENROUTER",
                capability="AI_STANDARD",
                model="approved/private-model",
                max_output_tokens=2000,
                input_cost_microusd_per_million=1000,
                output_cost_microusd_per_million=2000,
            ),
        ]
    )
    private_file = PrivateFile(
        owner_id=user_id,
        purpose="BASE_CV",
        bucket="private",
        object_key=f"users/{user_id}/cv.pdf",
        original_filename="cv.pdf",
        declared_content_type="application/pdf",
        declared_size=100,
        status="CLEAN",
    )
    session.add(private_file)
    session.flush()
    cv = BaseCv(
        user_id=user_id,
        file_id=private_file.id,
        name="Base CV",
        status="ACTIVE",
        extraction_status="SUCCEEDED",
        extracted_text="Built Python APIs at Fictional Previous Employer.",
    )
    session.add(cv)
    session.commit()
    return job.id, cv.id


def test_private_request_is_minimized_idempotent_and_metered(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        job_id, _ = seed_private_context(database)
        service = PrivateAiRequestService(database)
        artifact = service.request(
            user_id=str(USER_A),
            plan="PREMIUM",
            artifact_type="PROFILE_FIT",
            job_id=job_id,
            cv_id=None,
            correlation_id="c" * 36,
        )
        repeated = service.request(
            user_id=str(USER_A),
            plan="PREMIUM",
            artifact_type="PROFILE_FIT",
            job_id=job_id,
            cv_id=None,
            correlation_id="d" * 36,
        )
        event = database.scalar(select(OutboxEvent))

        assert repeated.id == artifact.id
        assert database.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        assert event is not None
        assert event.payload == {
            "artifact_id": artifact.id,
            "user_id": str(USER_A),
            "artifact_type": "PROFILE_FIT",
        }
        assert "Backend engineer" not in json.dumps(event.payload)

        provider = StaticProvider(
            {
                "readiness": "PROMISING",
                "summary": "Strong core match with one documented gap.",
                "strengths": ["Python"],
                "gaps": ["No Kubernetes evidence"],
                "blockers": [],
                "next_steps": ["Prepare a database example"],
            }
        )
        completed = PrivateAiOrchestrator(database, provider).process(
            artifact.id, correlation_id="c" * 36
        )
        operation = database.scalar(select(AiOperation))

        assert completed.status == "SUCCEEDED"
        assert completed.content is not None
        assert completed.content["readiness"] == "PROMISING"
        assert operation is not None
        assert operation.data_class == "PRIVATE_USER_DATA"
        assert operation.provider == "OPENROUTER"
        assert operation.total_tokens == 150
        assert provider.prompts and "Backend engineer" in provider.prompts[0]


def test_cv_suggestions_do_not_mutate_profile_until_explicit_accept(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        _, cv_id = seed_private_context(database)
        profile = database.get(ProfessionalProfile, str(USER_A))
        assert profile is not None
        assert len(profile.competencies) == 1
        artifact = PrivateAiRequestService(database).request(
            user_id=str(USER_A),
            plan="PREMIUM",
            artifact_type="CV_SUGGESTIONS",
            job_id=None,
            cv_id=cv_id,
            correlation_id="s" * 36,
        )
        provider = StaticProvider(
            {
                "suggestions": [
                    {
                        "category": "TECHNOLOGY",
                        "display_name": "FastAPI",
                        "canonical_id": None,
                        "proficiency": None,
                        "evidence": "Built Python APIs",
                        "confidence": 0.8,
                    }
                ]
            }
        )
        PrivateAiOrchestrator(database, provider).process(artifact.id, correlation_id="s" * 36)
        suggestion = database.scalar(select(ProfileSuggestion))

        database.refresh(profile)
        assert suggestion is not None
        assert profile.technologies_tools == []
        ProfileSuggestionService(database).decide(suggestion.id, str(USER_A), "ACCEPTED")
        database.refresh(profile)
        assert profile.technologies_tools == ["FastAPI"]
        assert suggestion.status == "ACCEPTED"
