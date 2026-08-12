from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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


class SourceAdapter(Protocol):
    key: str
    capabilities: AdapterCapabilities

    def validate_source(self, source_url: str | None) -> None: ...

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]: ...

    def health_check(self, content: str) -> bool: ...
