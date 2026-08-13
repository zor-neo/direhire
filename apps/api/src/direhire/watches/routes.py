from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.errors import AppError
from direhire.sources.csv_import import parse_source_csv
from direhire.sources.platforms import SEARCH_PLATFORMS, platform_as_dict, platforms_for_regions, resolve_location_regions
from direhire.watches.schemas import WatchCreate, WatchRead, WatchRunRead
from direhire.watches.service import WatchService

router = APIRouter(prefix="/watches", tags=["Job Watches"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


@router.get("/platforms")
def list_platforms(location: str | None = None) -> list[dict]:
    if location:
        regions = resolve_location_regions(location)
        platforms = platforms_for_regions(regions)
    else:
        platforms = list(SEARCH_PLATFORMS.values())
    return [platform_as_dict(p) for p in platforms]


@router.post("", response_model=WatchRead, status_code=status.HTTP_201_CREATED)
def create_watch(data: WatchCreate, user: User, session: DbSession) -> object:
    return WatchService(session).create(str(user.id), data)


@router.get("", response_model=list[WatchRead])
def list_watches(user: User, session: DbSession) -> object:
    return WatchService(session).list(str(user.id))


@router.get("/{watch_id}", response_model=WatchRead)
def get_watch(watch_id: str, user: User, session: DbSession) -> object:
    return WatchService(session).get(watch_id, str(user.id))


@router.put("/{watch_id}", response_model=WatchRead)
def replace_watch(watch_id: str, data: WatchCreate, user: User, session: DbSession) -> object:
    return WatchService(session).replace(watch_id, str(user.id), data)


@router.post("/{watch_id}/sources/import-csv", response_model=WatchRead)
async def import_watch_sources(
    watch_id: str, request: Request, user: User, session: DbSession
) -> object:
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].casefold()
    if content_type != "text/csv":
        raise AppError("CSV_INVALID", "Upload source data as UTF-8 CSV.", 415)
    sources = parse_source_csv(await request.body())
    return WatchService(session).import_sources(watch_id, str(user.id), sources)


@router.post("/{watch_id}/activate", response_model=WatchRead)
def activate_watch(watch_id: str, user: User, session: DbSession) -> object:
    return WatchService(session).activate(watch_id, str(user.id), user.plan)


@router.post("/{watch_id}/pause", response_model=WatchRead)
def pause_watch(watch_id: str, user: User, session: DbSession) -> object:
    return WatchService(session).pause(watch_id, str(user.id))


@router.post("/{watch_id}/archive", response_model=WatchRead)
def archive_watch(watch_id: str, user: User, session: DbSession) -> object:
    return WatchService(session).archive(watch_id, str(user.id))


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(watch_id: str, user: User, session: DbSession) -> Response:
    WatchService(session).delete(watch_id, str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{watch_id}/runs", response_model=WatchRunRead, status_code=status.HTTP_202_ACCEPTED)
def run_watch(watch_id: str, user: User, session: DbSession) -> object:
    return WatchService(session).request_manual_run(watch_id, str(user.id), user.plan)


@router.get("/{watch_id}/runs", response_model=list[WatchRunRead])
def list_watch_runs(watch_id: str, user: User, session: DbSession) -> object:
    return WatchService(session).list_runs(watch_id, str(user.id))
