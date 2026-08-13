from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from direhire.sources.detection import resolve_custom_source
from direhire.sources.platforms import SEARCH_PLATFORMS


class WatchStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class ExperienceLevel(StrEnum):
    ANY = "ANY"
    ENTRY = "ENTRY"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    EXECUTIVE = "EXECUTIVE"


class WatchSourceInput(BaseModel):
    source_kind: Literal["PLATFORM", "CUSTOM_URL"]
    platform_key: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_-]+$")
    adapter_key: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_-]+$")
    url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_source(self) -> "WatchSourceInput":
        if self.source_kind == "CUSTOM_URL":
            if not self.url:
                raise ValueError("Custom URL sources require a URL")
            if self.platform_key is not None:
                raise ValueError("Custom URL sources do not accept a platform key")
            self.adapter_key, self.url = resolve_custom_source(self.url, self.adapter_key)
        else:
            if not self.platform_key:
                raise ValueError("Platform sources require a platform key")
            if self.url is not None:
                raise ValueError("Platform sources do not accept a user URL")
            platform = SEARCH_PLATFORMS.get(self.platform_key)
            if platform is None:
                raise ValueError("Unsupported search platform")
            if platform.availability != "AVAILABLE":
                raise ValueError("Search platform is not currently available")
            self.adapter_key = platform.adapter_key
        return self


class WatchSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_kind: str
    platform_key: str | None
    adapter_key: str
    url: str | None


class WatchCreate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    target_terms: list[str] = Field(min_length=1, max_length=30)
    required_terms: list[str] = Field(default_factory=list, max_length=30)
    excluded_terms: list[str] = Field(default_factory=list, max_length=30)
    locations: list[str] = Field(default_factory=list, max_length=20)
    work_arrangements: list[Literal["ON_SITE", "HYBRID", "REMOTE"]] = Field(default_factory=list)
    employment_types: list[
        Literal["FULL_TIME", "PART_TIME", "CONTRACT", "TEMPORARY", "INTERNSHIP", "FREELANCE"]
    ] = Field(default_factory=list)
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.ANY)
    raw_intent: str | None = Field(default=None, max_length=2000)
    posting_age_days: int | None = Field(default=30)
    sources: list[WatchSourceInput] = Field(default_factory=list, max_length=20)

    @field_validator("target_terms", "required_terms", "excluded_terms", "locations")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(raw.strip().split())
            key = value.casefold()
            if value and key not in seen:
                normalized.append(value)
                seen.add(key)
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        normalized = " ".join((value or "").split())
        return normalized or None

    @field_validator("posting_age_days")
    @classmethod
    def validate_posting_age(cls, value: int | None) -> int | None:
        if value not in {3, 7, 14, 30, None}:
            raise ValueError("posting_age_days must be 3, 7, 14, 30, or null")
        return value

    @model_validator(mode="after")
    def validate_source_limits(self) -> "WatchCreate":
        platform_count = sum(source.source_kind == "PLATFORM" for source in self.sources)
        custom_count = sum(source.source_kind == "CUSTOM_URL" for source in self.sources)
        if platform_count > 3:
            raise ValueError("A Watch can contain up to 3 search platforms")
        if custom_count > 2:
            raise ValueError("A Watch can contain up to 2 custom URLs")
        return self


class WatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: WatchStatus
    target_terms: list[str]
    required_terms: list[str]
    excluded_terms: list[str]
    locations: list[str]
    work_arrangements: list[str]
    employment_types: list[str]
    experience_level: str
    raw_intent: str | None
    posting_age_days: int | None
    sources: list[WatchSourceRead]
    created_at: datetime
    updated_at: datetime


class WatchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    watch_id: str
    status: str
    trigger: str
    correlation_id: str
    created_at: datetime
    completed_at: datetime | None
    outcome: str | None
    sources_succeeded: int
    sources_failed: int
    discovered_count: int
    matched_count: int
