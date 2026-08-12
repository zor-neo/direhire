import hashlib
import time

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.contracts import (
    JOB_ANALYSIS_PROMPT_VERSION,
    JOB_DEMAND_SCHEMA_VERSION,
    AnalysisProvenance,
    JobDemandProfileContent,
    JobDemandProfileDocument,
)
from direhire.ai.providers import ProviderFailure, ProviderResponse, StructuredProvider
from direhire.ai.sanitizer import sanitize_public_job_description
from direhire.errors import AppError
from direhire.models import (
    AiModelPolicy,
    AiOperation,
    Job,
    JobDemandProfile,
    JobVersion,
    utcnow,
)


class AiOrchestrator:
    def __init__(self, session: Session, public_provider: StructuredProvider) -> None:
        self.session = session
        self.public_provider = public_provider

    def analyze_public_job(self, profile_id: str, *, correlation_id: str) -> JobDemandProfile:
        self.require_public_route("PUBLIC_AI_SAFE")
        profile = self.session.get(JobDemandProfile, profile_id)
        if profile is None:
            raise AppError("ANALYSIS_NOT_FOUND", "The analysis was not found.", 404)
        if profile.status == "SUCCEEDED":
            return profile
        row = self.session.execute(
            select(JobVersion, Job)
            .join(Job, Job.id == JobVersion.job_id)
            .where(JobVersion.id == profile.job_version_id)
        ).one_or_none()
        if row is None:
            raise AppError("JOB_NOT_FOUND", "The job is no longer available.", 404)
        version, job = row
        sanitized = sanitize_public_job_description(version.description)
        context = (
            f"Title: {job.title}\nCompany: {job.company}\nLocation: {job.location_raw}\n\n"
            f"Job description:\n{sanitized}"
        )
        input_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()
        profile.input_hash = input_hash
        policy = self.session.scalar(
            select(AiModelPolicy).where(
                AiModelPolicy.provider == "GEMINI",
                AiModelPolicy.capability == "AI_STANDARD",
                AiModelPolicy.enabled.is_(True),
            )
        )
        if policy is None:
            raise AppError(
                "AI_CAPABILITY_UNAVAILABLE",
                "Job analysis is temporarily unavailable.",
                503,
                retryable=True,
            )
        idempotency_key = (
            f"job-analysis:{profile.job_version_id}:{JOB_DEMAND_SCHEMA_VERSION}:"
            f"{JOB_ANALYSIS_PROMPT_VERSION}"
        )
        operation = self.session.scalar(
            select(AiOperation).where(AiOperation.idempotency_key == idempotency_key)
        )
        if operation is None:
            operation = AiOperation(
                idempotency_key=idempotency_key,
                task="JOB_ANALYSIS",
                capability="AI_STANDARD",
                data_class="PUBLIC_AI_SAFE",
                input_hash=input_hash,
                correlation_id=correlation_id,
            )
            self.session.add(operation)
            self.session.flush()
        profile.operation_id = operation.id
        if operation.status == "SUCCEEDED" and profile.profile is not None:
            profile.status = "SUCCEEDED"
            profile.error_code = None
            profile.updated_at = utcnow()
            operation.cache_hit = True
            self.session.commit()
            return profile

        operation.status = "RUNNING"
        operation.error_code = None
        profile.status = "RUNNING"
        started = time.monotonic()
        self.session.commit()
        prompt = self._prompt(context)
        response_schema = JobDemandProfileContent.model_json_schema()
        response: ProviderResponse | None = None
        content: JobDemandProfileContent | None = None
        for _ in range(2):
            try:
                response = self.public_provider.generate(
                    model=policy.model,
                    prompt=prompt,
                    response_schema=response_schema,
                    max_output_tokens=policy.max_output_tokens,
                )
            except ProviderFailure as exc:
                self._record_provider_failure(operation, profile, exc, started)
                raise AppError(
                    exc.code,
                    "Job analysis is temporarily unavailable.",
                    503,
                    retryable=exc.retryable,
                ) from exc
            self._meter_response(operation, response, policy)
            try:
                content = JobDemandProfileContent.model_validate_json(response.text)
                break
            except ValidationError:
                prompt = self._prompt(context, repair=True)
        if response is None or content is None:
            operation.status = "DEGRADED_FAILED"
            operation.error_code = "AI_OUTPUT_INVALID"
            operation.latency_ms += int((time.monotonic() - started) * 1000)
            operation.completed_at = utcnow()
            profile.status = "DEGRADED_FAILED"
            profile.error_code = "AI_OUTPUT_INVALID"
            profile.updated_at = utcnow()
            self.session.commit()
            return profile

        document = JobDemandProfileDocument(
            job_version_id=version.id,
            content=content,
            provenance=AnalysisProvenance(
                schema_version=JOB_DEMAND_SCHEMA_VERSION,
                prompt_version=JOB_ANALYSIS_PROMPT_VERSION,
                provider=response.provider,
                route_key=response.route_key,
                model=response.model,
                input_hash=input_hash,
                generated_at=utcnow(),
            ),
        )
        profile.profile = document.model_dump(mode="json")
        profile.status = "SUCCEEDED"
        profile.error_code = None
        profile.updated_at = utcnow()
        operation.status = "SUCCEEDED"
        operation.error_code = None
        operation.latency_ms += int((time.monotonic() - started) * 1000)
        operation.completed_at = utcnow()
        self.session.commit()
        return profile

    @staticmethod
    def require_public_route(data_class: str) -> None:
        if data_class != "PUBLIC_AI_SAFE":
            raise AppError(
                "AI_PRIVATE_ROUTE_UNAVAILABLE",
                "Private AI processing is not available through the public route.",
                503,
            )

    @staticmethod
    def _prompt(context: str, *, repair: bool = False) -> str:
        repair_instruction = (
            "Your previous attempt did not validate. Return every required field with the exact "
            "schema and no additional fields. "
            if repair
            else ""
        )
        return (
            "Analyze the complete public job description holistically, then extract evidence and "
            "reconcile contradictions. Return only the requested JSON object. Never invent a fact. "
            "Use UNCLEAR or null where evidence is absent. Remote does not imply worldwide, and "
            "absence of sponsorship language is unclear. Evidence must be a concise passage or "
            f"faithful paraphrase from the supplied job text. {repair_instruction}\n\n{context}"
        )

    @staticmethod
    def _meter_response(
        operation: AiOperation, response: ProviderResponse, policy: AiModelPolicy
    ) -> None:
        operation.provider_attempts += 1
        operation.provider = response.provider
        operation.route_key = response.route_key
        operation.model = response.model
        operation.prompt_tokens += response.usage.prompt_tokens
        operation.output_tokens += response.usage.output_tokens
        operation.total_tokens += response.usage.total_tokens
        operation.estimated_cost_microusd += round(
            (
                response.usage.prompt_tokens * policy.input_cost_microusd_per_million
                + response.usage.output_tokens * policy.output_cost_microusd_per_million
            )
            / 1_000_000
        )

    def _record_provider_failure(
        self,
        operation: AiOperation,
        profile: JobDemandProfile,
        failure: ProviderFailure,
        started: float,
    ) -> None:
        operation.provider_attempts += 1
        operation.status = "RETRYABLE_FAILED" if failure.retryable else "PERMANENT_FAILED"
        operation.error_code = failure.code
        operation.latency_ms += int((time.monotonic() - started) * 1000)
        operation.completed_at = utcnow()
        profile.status = operation.status
        profile.error_code = failure.code
        profile.updated_at = utcnow()
        self.session.commit()
