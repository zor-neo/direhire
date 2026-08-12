from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
ExternalChannel = Literal["NONE", "TELEGRAM", "WHATSAPP"]


class PreferenceUpdate(BaseModel):
    external_channel: ExternalChannel
    destination: str | None = Field(default=None, max_length=100)
    enabled: bool

    @model_validator(mode="after")
    def none_is_disabled(self) -> "PreferenceUpdate":
        if self.external_channel == "NONE" and self.enabled:
            raise ValueError("NONE cannot be enabled")
        return self


class PreferenceRead(BaseModel):
    external_channel: ExternalChannel
    enabled: bool
    destination_hint: str | None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


@router.get("/preference", response_model=PreferenceRead)
def get_preference(user: User, session: DbSession) -> object:
    return NotificationService(session).get_preference(str(user.id))


@router.put("/preference", response_model=PreferenceRead)
def set_preference(data: PreferenceUpdate, user: User, session: DbSession) -> object:
    return NotificationService(session).set_preference(
        str(user.id),
        channel=data.external_channel,
        destination=data.destination,
        enabled=data.enabled,
    )


@router.get("", response_model=list[NotificationRead])
def list_notifications(user: User, session: DbSession) -> object:
    return NotificationService(session).list_in_app(str(user.id))


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(notification_id: str, user: User, session: DbSession) -> object:
    return NotificationService(session).mark_read(notification_id, str(user.id))
