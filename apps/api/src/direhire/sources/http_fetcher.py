import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

from direhire.config import Settings
from direhire.errors import AppError
from direhire.models import WatchSource
from direhire.sources.validation import normalize_public_url


class SafePublicFetcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def __call__(self, source: WatchSource) -> str:
        if not source.url:
            raise AppError("SOURCE_UNSUPPORTED", "This source requires a dedicated adapter.", 422)
        return self.fetch_url(source.url)

    def fetch_url(self, raw_url: str) -> str:
        url = normalize_public_url(raw_url)
        self._validate_dns(url)
        try:
            with (
                httpx.Client(follow_redirects=False, timeout=15.0, trust_env=False) as client,
                client.stream("GET", url, headers={"User-Agent": "DireHire/0.1"}) as response,
            ):
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
                if content_type not in {
                    "text/html",
                    "application/json",
                    "application/ld+json",
                    "application/xml",
                    "application/rss+xml",
                    "text/xml",
                    "text/plain",
                }:
                    raise AppError(
                        "SOURCE_UNSUPPORTED", "The source content type is unsupported.", 422
                    )
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > self.settings.public_fetch_max_bytes:
                        raise AppError("SOURCE_TOO_LARGE", "The source response is too large.", 422)
        except AppError:
            raise
        except httpx.HTTPError as exc:
            raise AppError(
                "SOURCE_UNAVAILABLE", "The source is temporarily unavailable.", 503, retryable=True
            ) from exc
        try:
            return bytes(content).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(
                "SOURCE_UNSUPPORTED", "The source encoding is unsupported.", 422
            ) from exc

    @staticmethod
    def _validate_dns(url: str) -> None:
        host = urlsplit(url).hostname
        if not host:
            raise AppError("SOURCE_URL_INVALID", "Enter a valid public URL.", 422)
        try:
            addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise AppError(
                "SOURCE_UNAVAILABLE",
                "The source hostname could not be resolved.",
                503,
                retryable=True,
            ) from exc
        if not addresses or any(
            not ipaddress.ip_address(address[4][0]).is_global for address in addresses
        ):
            raise AppError(
                "SOURCE_URL_INVALID", "The source must resolve to a public address.", 422
            )
