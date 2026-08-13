import re

JOBTHAI_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?jobthai\.com/(?:[a-z]{2}/)?(?:company/)?job/(\d+)", re.IGNORECASE
)


def canonicalize_jobthai_url(raw_url: str) -> tuple[str, str] | None:
    """Extract external_job_id and produce canonical_url for JobThai.

    Example:
        'https://www.jobthai.com/en/company/job/1945537'
        -> ('1945537', 'https://www.jobthai.com/en/job/1945537')
    """
    match = JOBTHAI_URL_PATTERN.search(raw_url)
    if not match:
        return None
    job_id = match.group(1)
    canonical_url = f"https://www.jobthai.com/en/job/{job_id}"
    return job_id, canonical_url
