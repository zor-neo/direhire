from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    pagination: bool
    keyword_search: bool
    location_search: bool
    browser_required: bool
    full_description: bool


@dataclass(frozen=True, slots=True)
class DiscoveredJob:
    external_id: str
    url: str
    title: str
    company: str
    location_raw: str
    description: str
    posted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SearchQuery:
    keywords: tuple[str, ...]
    location: str | None
    experience_level: str | None
    posting_age_days: int | None
    page: int = 1


@dataclass(frozen=True, slots=True)
class SearchRequest:
    method: Literal["GET", "POST"]
    url: str
    headers: dict[str, str]
    json_body: dict[str, object] | None = None
    cache_seconds: int | None = None
    secret_headers: dict[str, str] = field(default_factory=dict)


class SourceAdapter(Protocol):
    key: str
    capabilities: AdapterCapabilities

    def validate_source(self, source_url: str | None) -> None: ...

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]: ...

    def health_check(self, content: str) -> bool: ...


class SearchAdapter(SourceAdapter, Protocol):
    def build_search_request(self, platform_key: str, query: SearchQuery) -> SearchRequest: ...
