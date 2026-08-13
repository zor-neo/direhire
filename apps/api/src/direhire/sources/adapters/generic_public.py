import json
import re
from contextlib import suppress
from html import unescape
from html.parser import HTMLParser

from direhire.sources.contracts import AdapterCapabilities, DiscoveredJob
from direhire.sources.validation import normalize_public_url


class GenericPublicAdapter:
    key = "generic_public"
    capabilities = AdapterCapabilities(
        pagination=False,
        keyword_search=False,
        location_search=False,
        browser_required=False,
        full_description=True,
    )

    def validate_source(self, source_url: str | None) -> None:
        if not source_url:
            raise ValueError("generic source requires a URL")
        normalize_public_url(source_url)

    def discover_jobs(self, content: str, source_url: str | None = None) -> list[DiscoveredJob]:
        parser = _JsonLdParser()
        parser.feed(content)
        jobs: list[DiscoveredJob] = []
        for document in parser.documents:
            items = document if isinstance(document, list) else [document]
            for item in items:
                if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                    continue
                organization = item.get("hiringOrganization") or {}
                location = item.get("jobLocation") or {}
                address = location.get("address") if isinstance(location, dict) else {}
                if not isinstance(organization, dict) or not isinstance(address, dict):
                    continue
                values = {
                    "external_id": str(item.get("identifier", {}).get("value", ""))
                    if isinstance(item.get("identifier"), dict)
                    else "",
                    "url": str(item.get("url", "")),
                    "title": str(item.get("title", "")),
                    "company": str(organization.get("name", "")),
                    "location": ", ".join(
                        str(address.get(key, ""))
                        for key in ("addressLocality", "addressCountry")
                        if address.get(key)
                    ),
                    "description": str(item.get("description", "")),
                }
                if all(values.values()):
                    jobs.append(
                        DiscoveredJob(
                            external_id=values["external_id"],
                            url=values["url"],
                            title=values["title"],
                            company=values["company"],
                            location_raw=values["location"],
                            description=values["description"],
                        )
                    )
        if jobs:
            return jobs

        # Fallback 1: __NEXT_DATA__ or inline JSON payload (e.g. JobThai direct page /en/job/{id})
        next_data_match = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', content, re.DOTALL
        )
        if next_data_match:
            with suppress(Exception):
                data = json.loads(next_data_match.group(1))
                apollo = data.get("props", {}).get("apolloState", {})
                rq = apollo.get("ROOT_QUERY", {}) if isinstance(apollo, dict) else {}
                for k, v in rq.items():
                    if "getJobRawData" in k and isinstance(v, dict) and "data" in v:
                        raw = v["data"]
                        if isinstance(raw, dict):
                            title = str(raw.get("title") or "").strip()
                            company_info = raw.get("company")
                            company = (
                                str(company_info.get("name") or "")
                                if isinstance(company_info, dict)
                                else ""
                            )
                            desc = str(raw.get("description") or "").strip()
                            props = raw.get("properties")
                            if isinstance(props, list) and props:
                                qual_str = "\n".join(f"- {p}" for p in props)
                                desc = (desc + "\n\nQualifications:\n" + qual_str).strip()
                            loc_info = raw.get("workLocation")
                            loc_str = ""
                            if isinstance(loc_info, dict):
                                prov = loc_info.get("province", {})
                                loc_str = (
                                    str(prov.get("name") or loc_info.get("address") or "")
                                    if isinstance(prov, dict)
                                    else ""
                                )
                            if title and desc:
                                return [
                                    DiscoveredJob(
                                        external_id=str(raw.get("_id") or ""),
                                        url=source_url or "",
                                        title=title,
                                        company=company or "Company",
                                        location_raw=loc_str or "Thailand",
                                        description=desc,
                                    )
                                ]

        # Fallback 2: OpenGraph or HTML meta tags
        og_title = re.search(
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']',
            content,
            re.IGNORECASE,
        )
        og_desc = re.search(
            r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\'](.*?)["\']',
            content,
            re.IGNORECASE,
        )
        title = unescape(og_title.group(1)) if og_title else None
        desc = unescape(og_desc.group(1)) if og_desc else None
        if not title:
            t_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            title = unescape(t_match.group(1)) if t_match else None
        if not desc:
            d_match = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
                content,
                re.IGNORECASE,
            )
            desc = unescape(d_match.group(1)) if d_match else None

        if title and desc and len(desc) > 30:
            clean_title = re.sub(r"\s*\|\s*.*$", "", title).strip()
            return [
                DiscoveredJob(
                    external_id="",
                    url=source_url or "",
                    title=clean_title or title,
                    company="Disclosed in listing",
                    location_raw="See job description",
                    description=desc,
                )
            ]

        return jobs

    def health_check(self, content: str) -> bool:
        return bool(self.discover_jobs(content))


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.buffer: list[str] = []
        self.documents: list[object] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.capture = tag == "script" and attributes.get("type") == "application/ld+json"
        if self.capture:
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.capture:
            with suppress(json.JSONDecodeError):
                self.documents.append(json.loads("".join(self.buffer)))
            self.capture = False
