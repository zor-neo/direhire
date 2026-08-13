from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from direhire.config import Settings
from direhire.errors import AppError
from direhire.models import SharedSourceFetch, WatchSource, utcnow
from direhire.sources.contracts import DiscoveredJob, SearchRequest, SourceAdapter
from direhire.sources.validation import normalize_public_url

ContentProvider = Callable[[WatchSource, SearchRequest | None], str]


class SharedFetchPending(AppError):
    def __init__(self) -> None:
        super().__init__(
            "SHARED_FETCH_PENDING",
            "A shared public source fetch is still in progress.",
            503,
            retryable=True,
        )


class SourceFetchCoalescer:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def discover(
        self,
        *,
        run_id: str,
        source: WatchSource,
        adapter: SourceAdapter,
        request: SearchRequest | None,
        content_provider: ContentProvider,
    ) -> list[DiscoveredJob]:
        now = datetime.now(UTC)
        normalized = (
            normalize_public_url(request.url)
            if request is not None
            else normalize_public_url(source.url)
            if source.url
            else source.source_key
        )
        request_material = ""
        if request is not None:
            request_material = json.dumps(request.json_body, sort_keys=True, separators=(",", ":"))
        method = request.method if request else "GET"
        key = hashlib.sha256(
            f"{adapter.key}|{method}|{normalized}|{request_material}".encode()
        ).hexdigest()
        shared = self.session.get(SharedSourceFetch, key)
        if shared is not None:
            result_expires = self._aware(shared.result_expires_at)
            if shared.status == "SUCCEEDED" and result_expires and result_expires > now:
                return self._deserialize(shared.results or [])
            lease_expires = self._aware(shared.lease_expires_at)
            if (
                shared.status == "RUNNING"
                and shared.owner_run_id != run_id
                and lease_expires is not None
                and lease_expires > now
            ):
                raise SharedFetchPending()
        else:
            shared = SharedSourceFetch(
                fetch_key=key,
                adapter_key=adapter.key,
                normalized_source=normalized,
            )
            self.session.add(shared)
        shared.status = "RUNNING"
        shared.owner_run_id = run_id
        shared.lease_expires_at = now + timedelta(seconds=self.settings.public_fetch_lease_seconds)
        shared.error_code = None
        shared.updated_at = utcnow()
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            shared = self.session.get(SharedSourceFetch, key)
            if shared is None:
                raise
            result_expires = self._aware(shared.result_expires_at)
            if shared.status == "SUCCEEDED" and result_expires and result_expires > now:
                return self._deserialize(shared.results or [])
            lease_expires = self._aware(shared.lease_expires_at)
            if shared.status == "RUNNING" and lease_expires and lease_expires > now:
                raise SharedFetchPending() from None
            shared.status = "RUNNING"
            shared.owner_run_id = run_id
            shared.lease_expires_at = now + timedelta(
                seconds=self.settings.public_fetch_lease_seconds
            )
            shared.error_code = None
            shared.updated_at = utcnow()
            self.session.commit()
        try:
            discovered = adapter.discover_jobs(content_provider(source, request), source.url)
        except Exception as exc:
            shared = self.session.get(SharedSourceFetch, key)
            if shared is not None:
                shared.status = "RETRYABLE_FAILED"
                shared.lease_expires_at = None
                shared.error_code = exc.code if isinstance(exc, AppError) else "SOURCE_UNAVAILABLE"
                shared.updated_at = utcnow()
                self.session.commit()
            raise
        shared = self.session.get(SharedSourceFetch, key)
        if shared is None:
            raise RuntimeError("shared fetch disappeared")
        shared.status = "SUCCEEDED"
        shared.owner_run_id = None
        shared.lease_expires_at = None
        shared.results = self._serialize(discovered)
        cache_seconds = (
            request.cache_seconds
            if request is not None and request.cache_seconds is not None
            else self.settings.public_fetch_cache_seconds
        )
        shared.result_expires_at = now + timedelta(seconds=cache_seconds)
        shared.error_code = None
        shared.updated_at = utcnow()
        self.session.commit()
        return discovered

    @staticmethod
    def _serialize(jobs: list[DiscoveredJob]) -> list[dict[str, object]]:
        return [
            {
                "external_id": job.external_id,
                "url": job.url,
                "title": job.title,
                "company": job.company,
                "location_raw": job.location_raw,
                "description": job.description,
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            }
            for job in jobs
        ]

    @staticmethod
    def _deserialize(values: list[dict[str, object]]) -> list[DiscoveredJob]:
        return [
            DiscoveredJob(
                external_id=str(value["external_id"]),
                url=str(value["url"]),
                title=str(value["title"]),
                company=str(value["company"]),
                location_raw=str(value["location_raw"]),
                description=str(value["description"]),
                posted_at=(
                    datetime.fromisoformat(str(value["posted_at"]))
                    if value.get("posted_at")
                    else None
                ),
            )
            for value in values
        ]

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
