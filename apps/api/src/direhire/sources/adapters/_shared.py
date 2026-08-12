import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from direhire.errors import AppError
from direhire.sources.validation import normalize_public_url


def json_document(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AppError("SOURCE_RESPONSE_INVALID", "The source returned invalid data.", 502) from exc


def public_endpoint(
    source_url: str | None,
    *,
    hosts: set[str] | None = None,
    host_suffix: str | None = None,
    path_pattern: str,
) -> str:
    if not source_url:
        raise AppError("SOURCE_URL_REQUIRED", "This source requires its public feed URL.", 422)
    normalized = normalize_public_url(source_url)
    parsed = urlsplit(normalized)
    host = parsed.hostname or ""
    host_allowed = (hosts is not None and host in hosts) or (
        host_suffix is not None and host.endswith(host_suffix) and host != host_suffix.lstrip(".")
    )
    if not host_allowed or re.fullmatch(path_pattern, parsed.path, re.IGNORECASE) is None:
        raise AppError(
            "SOURCE_URL_INVALID", "Enter the documented public feed URL for this source.", 422
        )
    return normalized


def text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def parse_iso_datetime(value: object) -> datetime | None:
    raw = text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def source_label(source_url: str | None, suffix: str) -> str:
    """Return the public board identifier when a feed omits an employer display name."""
    if not source_url:
        return "Employer"
    host = (urlsplit(source_url).hostname or "").removesuffix(suffix).strip(".")
    path_parts = [part for part in urlsplit(source_url).path.split("/") if part]
    token = host.split(".")[0] if host else (path_parts[-1] if path_parts else "Employer")
    return token.replace("-", " ").replace("_", " ").strip().title() or "Employer"
