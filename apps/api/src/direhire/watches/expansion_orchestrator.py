from __future__ import annotations

import json
import time

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.ai.providers import ProviderFailure, ProviderResponse, StructuredProvider
from direhire.errors import AppError
from direhire.models import AiModelPolicy, AiOperation, JobWatch, utcnow
from direhire.watches.expansion_contracts import (
    EXPANSION_PROMPT_VERSION,
    EXPANSION_SCHEMA_VERSION,
    QueryExpansionResult,
)
from direhire.watches.expansion_service import (
    criteria_hash,
    criteria_snapshot,
    expansion_metadata,
)


class WatchExpansionOrchestrator:
    def __init__(self, session: Session, private_provider: StructuredProvider) -> None:
        self.session = session
        self.private_provider = private_provider

    def process(self, watch_id: str, input_hash: str, *, correlation_id: str) -> JobWatch | None:
        watch = self.session.get(JobWatch, watch_id)
        if watch is None or criteria_hash(watch) != input_hash:
            return watch
        stored = watch.search_expansion
        if isinstance(stored, dict) and stored.get("criteria_hash") == input_hash:
            return watch
        policy = self.session.scalar(
            select(AiModelPolicy).where(
                AiModelPolicy.provider == "OPENROUTER",
                AiModelPolicy.capability == "AI_STANDARD",
                AiModelPolicy.enabled.is_(True),
            )
        )
        if policy is None:
            raise AppError(
                "AI_PRIVATE_CAPABILITY_UNAVAILABLE",
                "Search improvement is temporarily unavailable.",
                503,
                retryable=True,
            )
        operation = self._operation(watch, input_hash, correlation_id)
        operation.status = "RUNNING"
        operation.error_code = None
        self.session.commit()
        started = time.monotonic()
        prompt = self._prompt(watch, repair=False)
        parsed: QueryExpansionResult | None = None
        response: ProviderResponse | None = None
        for attempt in range(2):
            try:
                response = self.private_provider.generate(
                    model=policy.model,
                    prompt=prompt,
                    response_schema=QueryExpansionResult.model_json_schema(),
                    max_output_tokens=policy.max_output_tokens,
                )
            except ProviderFailure as exc:
                self._fail(operation, exc, started)
                raise AppError(
                    exc.code,
                    "Search improvement is temporarily unavailable.",
                    503,
                    retryable=exc.retryable,
                ) from exc
            self._meter(operation, response, policy)
            try:
                parsed = QueryExpansionResult.model_validate_json(response.text)
                break
            except ValidationError:
                if attempt == 0:
                    prompt = self._prompt(watch, repair=True)
        if parsed is None:
            operation.status = "DEGRADED_FAILED"
            operation.error_code = "AI_OUTPUT_INVALID"
            operation.latency_ms += int((time.monotonic() - started) * 1000)
            operation.completed_at = utcnow()
            self.session.commit()
            return watch

        self.session.refresh(watch)
        if criteria_hash(watch) != input_hash:
            operation.status = "CANCELLED"
            operation.error_code = "WATCH_CRITERIA_CHANGED"
            operation.completed_at = utcnow()
            self.session.commit()
            return watch
        parsed = self._only_requested_terms(parsed, watch.target_terms)
        generated_at = utcnow()
        watch.search_expansion = expansion_metadata(parsed, input_hash, generated_at.isoformat())
        watch.updated_at = generated_at
        operation.status = "SUCCEEDED"
        operation.error_code = None
        operation.latency_ms += int((time.monotonic() - started) * 1000)
        operation.completed_at = generated_at
        self.session.commit()
        return watch

    def _operation(self, watch: JobWatch, input_hash: str, correlation_id: str) -> AiOperation:
        key = (
            f"watch-expansion:{watch.id}:{input_hash[:32]}:"
            f"{EXPANSION_SCHEMA_VERSION}:{EXPANSION_PROMPT_VERSION}"
        )
        operation = self.session.scalar(
            select(AiOperation).where(AiOperation.idempotency_key == key)
        )
        if operation is None:
            operation = AiOperation(
                idempotency_key=key,
                task="WATCH_QUERY_EXPANSION",
                capability="AI_STANDARD",
                data_class="PRIVATE_USER_DATA",
                input_hash=input_hash,
                correlation_id=correlation_id,
            )
            self.session.add(operation)
            self.session.flush()
        return operation

    @staticmethod
    def _prompt(watch: JobWatch, *, repair: bool) -> str:
        repair_text = (
            "The previous response failed schema validation. Return the exact JSON schema. "
            if repair
            else ""
        )
        return (
            "Expand only the supplied job-search intent. Suggest concise alternative role names, "
            "technology names, abbreviations, and common spelling variants that improve retrieval. "
            "Keep each original target separate. Do not add unrelated occupations, employers, "
            "credentials, personal facts, or invented constraints. Return JSON only. "
            f"{repair_text}\n\nWatch criteria:\n"
            + json.dumps(criteria_snapshot(watch), sort_keys=True, ensure_ascii=False)
        )

    @staticmethod
    def _only_requested_terms(
        result: QueryExpansionResult, target_terms: list[str]
    ) -> QueryExpansionResult:
        allowed = {term.casefold() for term in target_terms}
        return result.model_copy(
            update={
                "target_expansions": [
                    expansion
                    for expansion in result.target_expansions
                    if expansion.original.casefold() in allowed
                ]
            }
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

    def _fail(self, operation: AiOperation, failure: ProviderFailure, started: float) -> None:
        operation.provider_attempts += 1
        operation.status = "RETRYABLE_FAILED" if failure.retryable else "PERMANENT_FAILED"
        operation.error_code = failure.code
        operation.latency_ms += int((time.monotonic() - started) * 1000)
        operation.completed_at = utcnow()
        self.session.commit()
