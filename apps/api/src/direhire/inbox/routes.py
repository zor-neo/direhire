from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.inbox.service import InboxService

router = APIRouter(prefix="/inbox", tags=["Job Inbox"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
InboxStatus = Literal["NEW", "VIEWED", "SAVED", "INTERESTED", "IGNORED", "ARCHIVED"]


class MatchedWatchRead(BaseModel):
    id: str
    name: str


class InboxItemRead(BaseModel):
    id: str
    job_id: str
    title: str
    company: str
    location: str
    source_url: str | None
    job_lifecycle: str
    status: InboxStatus
    created_at: datetime
    analysis_status: str
    analysis: dict[str, object] | None
    matched_watches: list[MatchedWatchRead] = []


class InboxStatusUpdate(BaseModel):
    status: InboxStatus


@router.get("", response_model=list[InboxItemRead])
def list_inbox(
    user: User,
    session: DbSession,
    watch_id: Annotated[str | None, Query(alias="watch_id")] = None,
) -> object:
    return InboxService(session).list(str(user.id), watch_id=watch_id)


@router.patch("/{user_job_id}/status", response_model=InboxItemRead)
def update_inbox_status(
    user_job_id: str, data: InboxStatusUpdate, user: User, session: DbSession
) -> object:
    return InboxService(session).set_status(user_job_id, str(user.id), data.status)


@router.post("/{user_job_id}/retry-analysis", response_model=InboxItemRead)
def retry_inbox_analysis(
    user_job_id: str, user: User, session: DbSession
) -> object:
    return InboxService(session).retry_analysis(user_job_id, str(user.id))
