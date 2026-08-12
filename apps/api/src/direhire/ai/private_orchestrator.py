from __future__ import annotations

import json
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.contracts import JobDemandProfileContent
from direhire.ai.private_contracts import (
    CareerPrepResult,
    CompanyResearchResult,
    CvProfileSuggestions,
    PrepareToApplyResult,
    ProfessionalAdviceResult,
    ProfileFitResult,
    TailoredCvResult,
)
from direhire.ai.providers import ProviderFailure, ProviderResponse, StructuredProvider
from direhire.errors import AppError
from direhire.models import (
    AiModelPolicy,
    AiOperation,
    PrivateAiArtifact,
    ProfileSuggestion,
    utcnow,
)

ResultModel = TypeVar("ResultModel", bound=BaseModel)

CONTRACTS: dict[str, type[BaseModel]] = {
    "CV_SUGGESTIONS": CvProfileSuggestions,
    "PROFILE_FIT": ProfileFitResult,
    "TAILORED_CV": TailoredCvResult,
    "PREPARE_TO_APPLY": PrepareToApplyResult,
    "CAREER_PREP": CareerPrepResult,
    "COMPANY_RESEARCH": CompanyResearchResult,
    "PROFESSIONAL_ADVICE": ProfessionalAdviceResult,
    "PASTED_JOB_ANALYSIS": JobDemandProfileContent,
}
CAPABILITIES = {
    "CV_SUGGESTIONS": "AI_STANDARD",
    "PROFILE_FIT": "AI_STANDARD",
    "TAILORED_CV": "AI_DOCUMENT",
    "PREPARE_TO_APPLY": "AI_DOCUMENT",
    "CAREER_PREP": "AI_DEEP_REASONING",
    "COMPANY_RESEARCH": "AI_DEEP_REASONING",
    "PROFESSIONAL_ADVICE": "AI_DEEP_REASONING",
    "PASTED_JOB_ANALYSIS": "AI_STANDARD",
}
SENSITIVE_TYPES = {
    "CV_SUGGESTIONS",
    "TAILORED_CV",
    "PREPARE_TO_APPLY",
    "CAREER_PREP",
    "COMPANY_RESEARCH",
}


class PrivateAiOrchestrator:
    def __init__(self, session: Session, private_provider: StructuredProvider) -> None:
        self.session = session
        self.private_provider = private_provider

    def process(self, artifact_id: str, *, correlation_id: str) -> PrivateAiArtifact:
        artifact = self.session.get(PrivateAiArtifact, artifact_id)
        if artifact is None:
            raise AppError(
                "PRIVATE_AI_ARTIFACT_NOT_FOUND", "The private request was not found.", 404
            )
        if artifact.status == "SUCCEEDED":
            return artifact
        contract = CONTRACTS.get(artifact.artifact_type)
        capability = CAPABILITIES.get(artifact.artifact_type)
        if contract is None or capability is None:
            raise AppError(
                "PRIVATE_AI_TASK_UNSUPPORTED", "This private request is unsupported.", 422
            )
        policy = self.session.scalar(
            select(AiModelPolicy).where(
                AiModelPolicy.provider == "OPENROUTER",
                AiModelPolicy.capability == capability,
                AiModelPolicy.enabled.is_(True),
            )
        )
        if policy is None:
            raise AppError(
                "AI_PRIVATE_CAPABILITY_UNAVAILABLE",
                "Private AI processing is temporarily unavailable.",
                503,
                retryable=True,
            )
        operation = self._operation(artifact, capability, correlation_id)
        artifact.operation_id = operation.id
        operation.status = "RUNNING"
        operation.error_code = None
        artifact.status = "RUNNING"
        artifact.error_code = None
        artifact.updated_at = utcnow()
        self.session.commit()
        started = time.monotonic()
        prompt = self._prompt(artifact, repair=False)
        parsed: BaseModel | None = None
        response: ProviderResponse | None = None
        for attempt in range(2):
            try:
                response = self.private_provider.generate(
                    model=policy.model,
                    prompt=prompt,
                    response_schema=contract.model_json_schema(),
                    max_output_tokens=policy.max_output_tokens,
                )
            except ProviderFailure as exc:
                self._fail_provider(artifact, operation, exc, started)
                raise AppError(
                    exc.code,
                    "Private AI processing is temporarily unavailable.",
                    503,
                    retryable=exc.retryable,
                ) from exc
            self._meter(operation, response, policy)
            try:
                parsed = contract.model_validate_json(response.text)
                break
            except ValidationError:
                if attempt == 0:
                    prompt = self._prompt(artifact, repair=True)
        if parsed is None:
            artifact.status = "DEGRADED_FAILED"
            artifact.error_code = "AI_OUTPUT_INVALID"
            artifact.updated_at = utcnow()
            operation.status = "DEGRADED_FAILED"
            operation.error_code = "AI_OUTPUT_INVALID"
            operation.latency_ms += int((time.monotonic() - started) * 1000)
            operation.completed_at = utcnow()
            self.session.commit()
            return artifact
        content = parsed.model_dump(mode="json")
        artifact.content = content
        if artifact.artifact_type in {"TAILORED_CV", "PREPARE_TO_APPLY"}:
            artifact.working_draft = content
        if artifact.artifact_type == "TAILORED_CV" and artifact.name is None:
            artifact.name = str(content["title"])
        if artifact.artifact_type == "CV_SUGGESTIONS":
            self._save_suggestions(artifact, parsed)
        artifact.status = "SUCCEEDED"
        artifact.error_code = None
        artifact.updated_at = utcnow()
        operation.status = "SUCCEEDED"
        operation.error_code = None
        operation.latency_ms += int((time.monotonic() - started) * 1000)
        operation.completed_at = utcnow()
        self.session.commit()
        return artifact

    def _operation(
        self, artifact: PrivateAiArtifact, capability: str, correlation_id: str
    ) -> AiOperation:
        key = f"private-artifact:{artifact.id}:{artifact.input_hash}"
        operation = self.session.scalar(
            select(AiOperation).where(AiOperation.idempotency_key == key)
        )
        if operation is None:
            operation = AiOperation(
                idempotency_key=key,
                task=artifact.artifact_type,
                capability=capability,
                data_class=(
                    "SENSITIVE_PRIVATE_DATA"
                    if artifact.artifact_type in SENSITIVE_TYPES
                    else "PRIVATE_USER_DATA"
                ),
                input_hash=artifact.input_hash,
                correlation_id=correlation_id,
            )
            self.session.add(operation)
            self.session.flush()
        return operation

    @staticmethod
    def _prompt(artifact: PrivateAiArtifact, *, repair: bool) -> str:
        repair_text = (
            "The prior response failed validation. Return every required field in the exact "
            "schema. "
            if repair
            else ""
        )
        task = artifact.artifact_type.replace("_", " ").lower()
        return (
            f"Complete the {task} task using only the supplied evidence. Return only the requested "
            "JSON. Never invent skills, credentials, roles, dates, achievements, eligibility, "
            "salary, or employer facts. Preserve uncertainty and identify gaps plainly. Use "
            "concise, "
            "professional English without inflated claims. Profile suggestions are proposals only. "
            f"{repair_text}\n\nEvidence:\n"
            + json.dumps(artifact.input_snapshot, sort_keys=True, ensure_ascii=False)
        )

    def _save_suggestions(self, artifact: PrivateAiArtifact, parsed: BaseModel) -> None:
        if not isinstance(parsed, CvProfileSuggestions):
            return
        existing = self.session.scalar(
            select(ProfileSuggestion.id).where(ProfileSuggestion.artifact_id == artifact.id)
        )
        if existing is not None:
            return
        for suggestion in parsed.suggestions:
            self.session.add(
                ProfileSuggestion(
                    user_id=artifact.user_id,
                    artifact_id=artifact.id,
                    category=suggestion.category,
                    suggestion=suggestion.model_dump(mode="json"),
                )
            )

    @staticmethod
    def _meter(operation: AiOperation, response: ProviderResponse, policy: AiModelPolicy) -> None:
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

    def _fail_provider(
        self,
        artifact: PrivateAiArtifact,
        operation: AiOperation,
        failure: ProviderFailure,
        started: float,
    ) -> None:
        status = "RETRYABLE_FAILED" if failure.retryable else "PERMANENT_FAILED"
        artifact.status = status
        artifact.error_code = failure.code
        artifact.updated_at = utcnow()
        operation.provider_attempts += 1
        operation.status = status
        operation.error_code = failure.code
        operation.latency_ms += int((time.monotonic() - started) * 1000)
        operation.completed_at = utcnow()
        self.session.commit()
