from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from direhire.audit.service import ActivityService
from direhire.auth import CurrentUser, current_user
from direhire.db import get_session

router = APIRouter(prefix="/account", tags=["Account"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    activity_type: str
    created_at: datetime


@router.get("/activity", response_model=list[ActivityRead])
def account_activity(user: User, session: DbSession) -> object:
    return ActivityService(session).list_for_owner(str(user.id))
