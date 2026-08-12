from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.audit.service import AuditService
from direhire.auth import CurrentUser, current_user
from direhire.auth.authorization import require_superadmin
from direhire.db import get_session
from direhire.errors import AppError
from direhire.models import PlatformControl, utcnow
from direhire.operations.service import OperationsService

router = APIRouter(prefix="/admin/operations", tags=["Admin Operations"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


class OperationsSummary(BaseModel):
    unpublished_outbox: int
    failed_outbox_publications: int
    active_watch_runs: int
    active_ai_operations: int
    active_shared_fetches: int
    ai_tokens_30d: int
    ai_cost_microusd_30d: int
    ai_cache_hits_30d: int


class StuckItem(BaseModel):
    kind: str
    id: str
    status: str
    event_type: str | None
    correlation_id: str
    error_code: str | None
    created_at: datetime


class PlatformControlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    enabled: bool
    updated_at: datetime


class PlatformControlUpdate(BaseModel):
    enabled: bool


@router.get("/summary", response_model=OperationsSummary)
def summary(user: User, session: DbSession) -> object:
    require_superadmin(user)
    return OperationsService(session).summary()


@router.get("/stuck", response_model=list[StuckItem])
def stuck(user: User, session: DbSession) -> object:
    require_superadmin(user)
    return OperationsService(session).stuck()


@router.get("/controls", response_model=list[PlatformControlRead])
def list_controls(user: User, session: DbSession) -> object:
    require_superadmin(user)
    return list(session.scalars(select(PlatformControl).order_by(PlatformControl.key)))


@router.put("/controls/{key}", response_model=PlatformControlRead)
def update_control(
    key: str,
    data: PlatformControlUpdate,
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    require_superadmin(user)
    allowed = {
        "JOB_DISCOVERY",
        "MANUAL_RUN",
        "PUBLIC_AI",
        "PRIVATE_AI",
        "DOCUMENT_GENERATION",
        "TELEGRAM",
        "WHATSAPP",
        "BROWSER_SCRAPING",
    }
    if key not in allowed:
        raise AppError("CONTROL_INVALID", "The platform control is invalid.", 422)
    control = session.get(PlatformControl, key)
    before = True if control is None else control.enabled
    if control is None:
        control = PlatformControl(key=key)
        session.add(control)
    control.enabled = data.enabled
    control.updated_at = utcnow()
    AuditService(session).record(
        actor_user_id=str(user.id),
        actor_role=user.role,
        action="PLATFORM_CONTROL_UPDATED",
        target_type="PLATFORM_CONTROL",
        target_id=key,
        result="SUCCEEDED",
        correlation_id=request.state.correlation_id,
        change_metadata={
            "before": {"enabled": before},
            "after": {"enabled": data.enabled},
        },
    )
    session.commit()
    return control
