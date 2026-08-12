from datetime import datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.scheduling.service import ScheduleService

router = APIRouter(prefix="/settings/schedule", tags=["Settings"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


class ScheduleUpdate(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)
    local_time: time
    enabled: bool = True


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    local_time: time
    enabled: bool
    next_run_at: datetime


@router.get("", response_model=ScheduleRead | None)
def get_schedule(user: User, session: DbSession) -> object:
    return ScheduleService(session).get(str(user.id))


@router.put("", response_model=ScheduleRead)
def update_schedule(data: ScheduleUpdate, user: User, session: DbSession) -> object:
    return ScheduleService(session).set_schedule(
        str(user.id), data.timezone, data.local_time, data.enabled
    )
