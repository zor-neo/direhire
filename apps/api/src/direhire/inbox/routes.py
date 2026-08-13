from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.inbox.service import InboxService

router = APIRouter(prefix="/inbox", tags=["Job Inbox"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
InboxStatus = Literal["NEW", "VIEWED", "SAVED", "INTERESTED", "IGNORED", "ARCHIVED"]


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


class InboxStatusUpdate(BaseModel):
    status: InboxStatus


@router.get("", response_model=list[InboxItemRead])
def list_inbox(user: User, session: DbSession) -> object:
    return InboxService(session).list(str(user.id))


@router.patch("/{user_job_id}/status", response_model=InboxItemRead)
def update_inbox_status(
    user_job_id: str, data: InboxStatusUpdate, user: User, session: DbSession
) -> object:
    return InboxService(session).set_status(user_job_id, str(user.id), data.status)
