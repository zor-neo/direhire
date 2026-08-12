from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.audit.service import AuditService
from direhire.auth import CurrentUser, current_user
from direhire.auth.authorization import require_superadmin
from direhire.db import get_session
from direhire.errors import AppError
from direhire.models import PlanEntitlement, utcnow

router = APIRouter(prefix="/admin/entitlements", tags=["Admin Entitlements"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
Plan = Literal["FREE", "PREMIUM"]


class EntitlementUpdate(BaseModel):
    enabled: bool
    limit_value: int = Field(ge=0, le=10000)


class EntitlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: str
    entitlement_key: str
    enabled: bool
    limit_value: int
    updated_at: datetime


@router.get("", response_model=list[EntitlementRead])
def list_plan_entitlements(user: User, session: DbSession) -> object:
    require_superadmin(user)
    return list(
        session.scalars(
            select(PlanEntitlement).order_by(PlanEntitlement.plan, PlanEntitlement.entitlement_key)
        )
    )


@router.put("/plans/{plan}/{entitlement_key}", response_model=EntitlementRead)
def update_plan_entitlement(
    plan: Plan,
    entitlement_key: str,
    data: EntitlementUpdate,
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    require_superadmin(user)
    if not entitlement_key or len(entitlement_key) > 80:
        raise AppError("VALIDATION_ERROR", "The entitlement key is invalid.", 422)
    entitlement = session.scalar(
        select(PlanEntitlement).where(
            PlanEntitlement.plan == plan,
            PlanEntitlement.entitlement_key == entitlement_key,
        )
    )
    previous = None
    if entitlement is None:
        entitlement = PlanEntitlement(plan=plan, entitlement_key=entitlement_key)
        session.add(entitlement)
    else:
        previous = {"enabled": entitlement.enabled, "limit_value": entitlement.limit_value}
    entitlement.enabled = data.enabled
    entitlement.limit_value = data.limit_value
    entitlement.updated_at = utcnow()
    AuditService(session).record(
        actor_user_id=str(user.id),
        actor_role=user.role,
        action="ENTITLEMENT_UPDATED",
        target_type="PLAN_ENTITLEMENT",
        target_id=f"{plan}:{entitlement_key}",
        result="SUCCEEDED",
        correlation_id=request.state.correlation_id,
        change_metadata={
            "before": previous,
            "after": {"enabled": data.enabled, "limit_value": data.limit_value},
        },
    )
    session.commit()
    return entitlement
