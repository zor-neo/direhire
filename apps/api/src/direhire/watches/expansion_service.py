from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from direhire.models import JobWatch, OutboxEvent
from direhire.watches.expansion_contracts import (
    EXPANSION_PROMPT_VERSION,
    EXPANSION_SCHEMA_VERSION,
    QueryExpansionResult,
)


def criteria_snapshot(watch: JobWatch) -> dict[str, object]:
    return {
        "target_terms": list(watch.target_terms),
        "required_terms": list(watch.required_terms),
        "excluded_terms": list(watch.excluded_terms),
        "locations": list(watch.locations),
        "work_arrangements": list(watch.work_arrangements),
        "employment_types": list(watch.employment_types),
        "experience_level": watch.experience_level,
        "posting_age_days": watch.posting_age_days,
    }


def criteria_hash(watch: JobWatch) -> str:
    serialized = json.dumps(criteria_snapshot(watch), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def queue_watch_expansion(
    session: Session, watch: JobWatch, *, correlation_id: str | None = None
) -> OutboxEvent:
    input_hash = criteria_hash(watch)
    event = OutboxEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type="watch.query-expansion.requested",
        schema_version=1,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload={"watch_id": watch.id, "input_hash": input_hash},
    )
    session.add(event)
    return event


def expanded_search_keywords(watch: JobWatch) -> tuple[str, ...]:
    values = list(watch.target_terms)
    stored = watch.search_expansion
    if not isinstance(stored, dict) or stored.get("criteria_hash") != criteria_hash(watch):
        return tuple(values)
    try:
        result = QueryExpansionResult.model_validate(stored.get("result"))
    except (TypeError, ValueError):
        return tuple(values)
    allowed_originals = {term.casefold() for term in watch.target_terms}
    for expansion in result.target_expansions:
        if expansion.original.casefold() not in allowed_originals:
            continue
        values.extend(expansion.variants)
    deduplicated: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            deduplicated.append(value)
            seen.add(key)
    return tuple(deduplicated)


def expansion_metadata(result: QueryExpansionResult, input_hash: str, generated_at: str) -> dict:
    return {
        "schema_version": EXPANSION_SCHEMA_VERSION,
        "prompt_version": EXPANSION_PROMPT_VERSION,
        "criteria_hash": input_hash,
        "generated_at": generated_at,
        "result": result.model_dump(mode="json"),
    }
