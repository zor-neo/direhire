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
from direhire.models import SourcePolicy, utcnow
from direhire.sources.policy_service import SourcePolicyService

router = APIRouter(prefix="/admin/source-policies", tags=["Admin Source Operations"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


class SourcePolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adapter_key: str
    enabled: bool
    health: str
    max_concurrency: int
    minimum_delay_ms: int
    browser_allowed: bool
    failure_count: int
    failure_threshold: int
    cooldown_seconds: int
    cooldown_until: datetime | None
    updated_at: datetime


class SourcePolicyUpdate(BaseModel):
    enabled: bool
    max_concurrency: int = Field(ge=1, le=20)
    minimum_delay_ms: int = Field(ge=0, le=3_600_000)
    browser_allowed: bool
    failure_threshold: int = Field(ge=1, le=100)
    cooldown_seconds: int = Field(ge=30, le=86_400)


class SourcePolicyAction(BaseModel):
    action: Literal["DISABLE", "ENABLE", "MARK_DEGRADED", "PAUSE", "RESUME", "CLEAR_FAILURES"]


@router.get("", response_model=list[SourcePolicyRead])
def list_source_policies(user: User, session: DbSession) -> object:
    require_superadmin(user)
    return list(session.scalars(select(SourcePolicy).order_by(SourcePolicy.adapter_key)))


@router.put("/{adapter_key}", response_model=SourcePolicyRead)
def update_source_policy(
    adapter_key: str,
    data: SourcePolicyUpdate,
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    require_superadmin(user)
    policy = SourcePolicyService(session).get_or_create(_validate_adapter_key(adapter_key))
    before = _snapshot(policy)
    for key, value in data.model_dump().items():
        setattr(policy, key, value)
    if not policy.enabled:
        policy.health = "DISABLED"
        policy.cooldown_until = None
    elif policy.health == "DISABLED":
        policy.health = "HEALTHY"
    policy.updated_at = utcnow()
    _audit(session, request, user, policy, "SOURCE_POLICY_UPDATED", before)
    session.commit()
    return policy


@router.post("/{adapter_key}/actions", response_model=SourcePolicyRead)
def control_source_policy(
    adapter_key: str,
    data: SourcePolicyAction,
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    require_superadmin(user)
    policy = SourcePolicyService(session).get_or_create(_validate_adapter_key(adapter_key))
    before = _snapshot(policy)
    if data.action == "DISABLE":
        policy.enabled = False
        policy.health = "DISABLED"
        policy.cooldown_until = None
    elif data.action == "ENABLE":
        policy.enabled = True
        policy.health = "HEALTHY"
        policy.failure_count = 0
        policy.cooldown_until = None
    elif data.action == "MARK_DEGRADED":
        policy.health = "DEGRADED"
    elif data.action == "PAUSE":
        policy.health = "TEMPORARILY_PAUSED"
        policy.cooldown_until = None
    elif data.action == "RESUME":
        policy.enabled = True
        policy.health = "HEALTHY"
        policy.cooldown_until = None
    else:
        policy.failure_count = 0
        policy.cooldown_until = None
        policy.health = "HEALTHY" if policy.enabled else "DISABLED"
    policy.updated_at = utcnow()
    _audit(session, request, user, policy, f"SOURCE_{data.action}", before)
    session.commit()
    return policy


def _validate_adapter_key(adapter_key: str) -> str:
    if (
        not adapter_key
        or len(adapter_key) > 64
        or not all(character.isalnum() or character in {"_", "-"} for character in adapter_key)
    ):
        raise AppError("VALIDATION_ERROR", "The adapter key is invalid.", 422)
    return adapter_key


def _snapshot(policy: SourcePolicy) -> dict[str, object]:
    return {
        "enabled": policy.enabled,
        "health": policy.health,
        "max_concurrency": policy.max_concurrency,
        "minimum_delay_ms": policy.minimum_delay_ms,
        "browser_allowed": policy.browser_allowed,
        "failure_count": policy.failure_count,
        "failure_threshold": policy.failure_threshold,
        "cooldown_seconds": policy.cooldown_seconds,
    }


def _audit(
    session: Session,
    request: Request,
    user: CurrentUser,
    policy: SourcePolicy,
    action: str,
    before: dict[str, object],
) -> None:
    AuditService(session).record(
        actor_user_id=str(user.id),
        actor_role=user.role,
        action=action,
        target_type="SOURCE_POLICY",
        target_id=policy.adapter_key,
        result="SUCCEEDED",
        correlation_id=request.state.correlation_id,
        change_metadata={"before": before, "after": _snapshot(policy)},
    )
