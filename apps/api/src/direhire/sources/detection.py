from __future__ import annotations

from urllib.parse import urlsplit

from direhire.sources.validation import normalize_public_url


def resolve_custom_source(raw_url: str, adapter_hint: str | None = None) -> tuple[str, str]:
    """Resolve a human-facing public careers URL to a supported public feed."""
    url = normalize_public_url(raw_url)
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    parts = [part for part in parsed.path.split("/") if part]

    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
        token = parts[0]
        return "greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    if host == "boards-api.greenhouse.io":
        return "greenhouse", url
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and parts:
        api_host = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        return "lever", f"https://{api_host}/v0/postings/{parts[0]}?mode=json"
    if host in {"api.lever.co", "api.eu.lever.co"}:
        return "lever", url
    if host in {"jobs.ashbyhq.com", "jobs.ashby.io"} and parts:
        return "ashby", f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}"
    if host == "api.ashbyhq.com":
        return "ashby", url
    if host.endswith(".recruitee.com"):
        return "recruitee", f"{parsed.scheme}://{parsed.netloc}/api/offers"
    if host.endswith(".jobs.personio.de"):
        return "personio", f"{parsed.scheme}://{parsed.netloc}/xml"
    if host.endswith(".pinpointhq.com"):
        return "pinpoint", f"{parsed.scheme}://{parsed.netloc}/jobs.rss"
    if host == "apply.workable.com":
        if len(parts) >= 5 and parts[:4] == ["api", "v1", "widget", "accounts"]:
            return "workable", f"https://apply.workable.com/api/v1/widget/accounts/{parts[4]}?details=true"
        if parts and parts[0] not in {"api", "j"}:
            return "workable", f"https://apply.workable.com/api/v1/widget/accounts/{parts[0]}?details=true"
    if host.endswith(".example.invalid") and adapter_hint:
        return adapter_hint, url
    return "generic_public", url
