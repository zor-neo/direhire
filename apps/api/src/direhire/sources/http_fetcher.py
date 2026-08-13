import ipaddress
import json
import socket
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from direhire.config import Settings
from direhire.errors import AppError
from direhire.models import WatchSource
from direhire.sources.contracts import SearchRequest
from direhire.sources.validation import normalize_public_url


class SecretProvider(Protocol):
    def get(self, parameter_name: str) -> str: ...


class SsmSecretProvider:
    def __init__(self) -> None:
        import boto3

        self.client = boto3.client("ssm")

    def get(self, parameter_name: str) -> str:
        response = self.client.get_parameter(Name=parameter_name, WithDecryption=True)
        return str(response["Parameter"]["Value"])


class SafePublicFetcher:
    def __init__(self, settings: Settings, secret_provider: SecretProvider | None = None) -> None:
        self.settings = settings
        self.secret_provider = secret_provider

    def __call__(self, source: WatchSource, request: SearchRequest | None = None) -> str:
        if request is not None:
            return self.fetch_request(request)
        if not source.url:
            raise AppError("SOURCE_UNSUPPORTED", "This source requires a dedicated adapter.", 422)
        return self.fetch_url(source.url)

    def fetch_url(self, raw_url: str) -> str:
        return self.fetch_request(SearchRequest(method="GET", url=raw_url, headers={}))

    def fetch_request(self, request: SearchRequest) -> str:
        if request.method not in {"GET", "POST"}:
            raise AppError("SOURCE_UNSUPPORTED", "The source request method is unsupported.", 422)
        allowed_headers = {"accept", "content-type", "client-name", "user-agent"}
        allowed_secret_headers = {"authorization-key", "user-agent"}
        if any(key.casefold() not in allowed_headers for key in request.headers) or any(
            key.casefold() not in allowed_secret_headers for key in request.secret_headers
        ):
            raise AppError("SOURCE_UNSUPPORTED", "The source request headers are unsupported.", 422)
        if request.method == "GET" and request.json_body is not None:
            raise AppError("SOURCE_UNSUPPORTED", "GET source requests cannot contain JSON.", 422)
        url = normalize_public_url(request.url)
        self._validate_dns(url)
        body = (
            json.dumps(request.json_body).encode("utf-8") if request.json_body is not None else None
        )
        headers = {"User-Agent": "DireHire/0.1", **request.headers}
        if request.secret_headers:
            provider = self.secret_provider or SsmSecretProvider()
            headers.update(
                {
                    header: provider.get(parameter_name)
                    for header, parameter_name in request.secret_headers.items()
                }
            )
        try:
            with (
                httpx.Client(follow_redirects=False, timeout=15.0, trust_env=False) as client,
                client.stream(request.method, url, headers=headers, content=body) as response,
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
