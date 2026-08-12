import ipaddress
from urllib.parse import urlsplit, urlunsplit

from direhire.errors import AppError


def normalize_public_url(raw_url: str) -> str:
    try:
        parsed = urlsplit(raw_url.strip())
    except ValueError as exc:
        raise _invalid_url() from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _invalid_url()
    if parsed.username or parsed.password:
        raise _invalid_url()
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise _invalid_url()
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise _invalid_url()
    port = parsed.port
    if port not in {None, 80, 443}:
        raise _invalid_url()
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunsplit((parsed.scheme.casefold(), netloc, parsed.path or "/", parsed.query, ""))


def _invalid_url() -> AppError:
    return AppError("SOURCE_URL_INVALID", "Enter a supported public HTTP or HTTPS URL.", 422)
