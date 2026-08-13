from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from direhire.models import JobWatch
from direhire.sources.platforms import resolve_location_regions


@dataclass(frozen=True, slots=True)
class ExternalSearch:
    key: str
    name: str
    coverage: str
    url: str


def external_searches_for(watch: JobWatch) -> list[ExternalSearch]:
    """Build user-initiated search links without fetching an external site."""
    keywords = " ".join(watch.target_terms)
    location = watch.locations[0] if watch.locations else ""
    regions = set(resolve_location_regions(location))
    searches: list[ExternalSearch] = []

    searches.extend(_seek_searches(keywords, location, regions))
    if "KH" in regions:
        searches.extend(
            (
                ExternalSearch(
                    "bongthom",
                    "BongThom",
                    "Cambodia",
                    "https://bongthom.com/job_list.html",
                ),
                ExternalSearch(
                    "jobnet-cambodia",
                    "JobNet Cambodia",
                    "Cambodia",
                    "https://www.jobnet.com.kh/jobs-in-cambodia",
                ),
                ExternalSearch(
                    "khmer24",
                    "Khmer24 Jobs",
                    "Cambodia",
                    "https://www.khmer24.com/en/jobs",
                ),
            )
        )
    if regions.intersection({"US", "GB"}):
        searches.append(
            ExternalSearch(
                "dice",
                "Dice",
                "US and UK technology roles",
                _url("https://www.dice.com/jobs", q=keywords, location=location),
            )
        )
    if regions.intersection({"FR", "DE", "ES", "NL", "GB", "CZ", "SK"}):
        searches.append(
            ExternalSearch(
                "wttj",
                "Welcome to the Jungle",
                "Europe",
                "https://www.welcometothejungle.com/en-GB/jobs",
            )
        )

    searches.extend(
        (
            ExternalSearch(
                "linkedin",
                "LinkedIn Jobs",
                "Global",
                _url(
                    "https://www.linkedin.com/jobs/search/",
                    keywords=keywords,
                    location=location,
                ),
            ),
            ExternalSearch(
                "indeed",
                "Indeed",
                "Global",
                _url("https://www.indeed.com/jobs", q=keywords, l=location),
            ),
        )
    )
    return searches


def _seek_searches(
    keywords: str, location: str, regions: set[str]
) -> list[ExternalSearch]:
    endpoints = {
        "MY": ("jobstreet-my", "JobStreet Malaysia", "https://my.jobstreet.com/jobs"),
        "SG": ("jobstreet-sg", "JobStreet Singapore", "https://sg.jobstreet.com/jobs"),
        "ID": ("jobstreet-id", "JobStreet Indonesia", "https://id.jobstreet.com/id/jobs"),
        "PH": ("jobstreet-ph", "JobStreet Philippines", "https://ph.jobstreet.com/jobs"),
        "TH": ("jobsdb-th", "JobsDB Thailand", "https://th.jobsdb.com/jobs"),
        "HK": ("jobsdb-hk", "JobsDB Hong Kong", "https://hk.jobsdb.com/jobs"),
    }
    return [
        ExternalSearch(key, name, region, _url(endpoint, keywords=keywords, where=location))
        for region, (key, name, endpoint) in endpoints.items()
        if region in regions
    ]


def _url(base: str, **parameters: str) -> str:
    values = {key: value for key, value in parameters.items() if value}
    return f"{base}?{urlencode(values)}" if values else base
