from pydantic import Field, field_validator

from direhire.ai.contracts import StrictModel

EXPANSION_SCHEMA_VERSION = 1
EXPANSION_PROMPT_VERSION = "watch-query-expansion-v1"


class TermExpansion(StrictModel):
    original: str = Field(min_length=1, max_length=160)
    variants: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("original")
    @classmethod
    def normalize_original(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("variants")
    @classmethod
    def normalize_variants(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(raw.split())
            key = value.casefold()
            if value and key not in seen:
                result.append(value)
                seen.add(key)
        return result


class QueryExpansionResult(StrictModel):
    target_expansions: list[TermExpansion] = Field(default_factory=list, max_length=30)
    location_variants: list[str] = Field(default_factory=list, max_length=10)
    experience_keywords: list[str] = Field(default_factory=list, max_length=10)
    schema_version: int = EXPANSION_SCHEMA_VERSION

    @field_validator("location_variants", "experience_keywords")
    @classmethod
    def normalize_strings(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(raw.split())
            key = value.casefold()
            if value and key not in seen:
                result.append(value)
                seen.add(key)
        return result
