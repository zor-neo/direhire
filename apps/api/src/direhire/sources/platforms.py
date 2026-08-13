"""Static registry of supported search platforms and their metadata.

Search platforms are job boards/aggregators where we can search by keywords
and location (e.g., JobStreet, JobsDB, JobThai). These are distinct from
employer ATS adapters (Greenhouse, Lever, etc.) which crawl a specific
company's career page.

The registry is static in code because each platform requires a dedicated
adapter implementation. New platforms are added here when their adapter
is ready and fixture-tested.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SearchPlatform:
    key: str
    name: str
    adapter_key: str
    regions: tuple[str, ...]
    tier: str  # "A" = API/XHR, "B" = JSON-LD, "C" = browser scraping
    search_capable: bool
    availability: str
    logo_filename: str
    description: str = ""


# Platforms are ordered by priority / coverage breadth.
SEARCH_PLATFORMS: dict[str, SearchPlatform] = {
    "jobstreet": SearchPlatform(
        key="jobstreet",
        name="JobStreet",
        adapter_key="seek_search",
        regions=("MY", "SG", "ID", "PH"),
        tier="A",
        search_capable=True,
        availability="PAUSED",
        logo_filename="jobstreet.svg",
        description="Jobs across Malaysia, Singapore, Indonesia, Philippines",
    ),
    "jobsdb": SearchPlatform(
        key="jobsdb",
        name="JobsDB",
        adapter_key="seek_search",
        regions=("TH", "HK"),
        tier="A",
        search_capable=True,
        availability="PAUSED",
        logo_filename="jobsdb.svg",
        description="Jobs across Thailand and Hong Kong",
    ),
    "jobthai": SearchPlatform(
        key="jobthai",
        name="JobThai",
        adapter_key="jobthai",
        regions=("TH",),
        tier="A",
        search_capable=True,
        availability="AVAILABLE",
        logo_filename="jobthai.svg",
        description="Thailand's leading job platform",
    ),
    "remotive": SearchPlatform(
        key="remotive",
        name="Remotive",
        adapter_key="remotive",
        regions=("GLOBAL",),
        tier="A",
        search_capable=True,
        availability="AVAILABLE",
        logo_filename="remotive.svg",
        description="Remote roles worldwide, attributed to Remotive",
    ),
    "glassdoor": SearchPlatform(
        key="glassdoor",
        name="Glassdoor",
        adapter_key="glassdoor",
        regions=("US", "GB", "SG", "MY", "TH", "ID", "PH", "HK", "JP", "DE", "FR"),
        tier="B",
        search_capable=True,
        availability="UNAVAILABLE",
        logo_filename="glassdoor.svg",
        description="Global jobs with company reviews and salary data",
    ),
    "dice": SearchPlatform(
        key="dice",
        name="Dice",
        adapter_key="dice",
        regions=("US", "GB"),
        tier="B",
        search_capable=True,
        availability="UNAVAILABLE",
        logo_filename="dice.svg",
        description="Technology and engineering jobs",
    ),
    "wttj": SearchPlatform(
        key="wttj",
        name="Welcome to the Jungle",
        adapter_key="wttj",
        regions=("FR", "DE", "ES", "NL", "GB", "CZ", "SK"),
        tier="A",
        search_capable=True,
        availability="UNAVAILABLE",
        logo_filename="wttj.svg",
        description="European tech and startup jobs",
    ),
}

# Region display names for the frontend.
REGION_NAMES: dict[str, str] = {
    "MY": "Malaysia",
    "SG": "Singapore",
    "TH": "Thailand",
    "ID": "Indonesia",
    "PH": "Philippines",
    "HK": "Hong Kong",
    "JP": "Japan",
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "NL": "Netherlands",
    "CZ": "Czech Republic",
    "SK": "Slovakia",
    "KH": "Cambodia",
}

# Mapping from common location inputs to region codes.
# Used to recommend platforms based on user's location input.
LOCATION_TO_REGIONS: dict[str, list[str]] = {
    "malaysia": ["MY"],
    "kuala lumpur": ["MY"],
    "penang": ["MY"],
    "johor": ["MY"],
    "singapore": ["SG"],
    "thailand": ["TH"],
    "bangkok": ["TH"],
    "chiang mai": ["TH"],
    "indonesia": ["ID"],
    "jakarta": ["ID"],
    "philippines": ["PH"],
    "manila": ["PH"],
    "hong kong": ["HK"],
    "cambodia": ["KH"],
    "phnom penh": ["KH"],
    "japan": ["JP"],
    "tokyo": ["JP"],
    "united states": ["US"],
    "usa": ["US"],
    "new york": ["US"],
    "san francisco": ["US"],
    "united kingdom": ["GB"],
    "uk": ["GB"],
    "london": ["GB"],
    "germany": ["DE"],
    "berlin": ["DE"],
    "france": ["FR"],
    "paris": ["FR"],
    "europe": ["FR", "DE", "ES", "NL", "GB", "CZ", "SK"],
    "eu": ["FR", "DE", "ES", "NL", "GB", "CZ", "SK"],
    "remote": [],  # No region filter — show all platforms
    "remote apac": ["MY", "SG", "TH", "ID", "PH", "HK", "JP"],
    "remote europe": ["FR", "DE", "ES", "NL", "GB", "CZ", "SK"],
    "apac": ["MY", "SG", "TH", "ID", "PH", "HK", "JP"],
    "sea": ["MY", "SG", "TH", "ID", "PH", "KH"],
    "southeast asia": ["MY", "SG", "TH", "ID", "PH", "KH"],
}


def platforms_for_regions(region_codes: list[str]) -> list[SearchPlatform]:
    """Return platforms that cover any of the given regions, ordered by match breadth."""
    if not region_codes:
        return list(SEARCH_PLATFORMS.values())
    return [
        platform
        for platform in SEARCH_PLATFORMS.values()
        if any(region in platform.regions for region in region_codes)
    ]


def available_platforms() -> list[SearchPlatform]:
    """Return only platforms backed by an operational, fixture-tested adapter."""
    return [
        platform for platform in SEARCH_PLATFORMS.values() if platform.availability == "AVAILABLE"
    ]


def resolve_location_regions(location: str) -> list[str]:
    """Resolve a user-typed location string to region codes."""
    key = " ".join(location.strip().lower().split())
    return LOCATION_TO_REGIONS.get(key, [])


def platform_as_dict(platform: SearchPlatform) -> dict[str, object]:
    """Serialize a platform for API response."""
    data = asdict(platform)
    data["regions"] = list(platform.regions)
    return data
