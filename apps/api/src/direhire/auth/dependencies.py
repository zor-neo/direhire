from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from direhire.auth.session_service import SessionService
from direhire.config import get_settings
from direhire.db import get_session
from direhire.errors import AppError


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    role: str = "USER"
    plan: str = "FREE"
    session_id: UUID | None = None


DbSession = Annotated[Session, Depends(get_session)]


def _resolve_current_user(
    request: Request, session: Session, *, enforce_privileged_mfa: bool
) -> CurrentUser:
    settings = get_settings()
    if (
        settings.allow_insecure_dev_auth
        and settings.environment in {"development", "test"}
        and (header_user_id := request.headers.get("X-DireHire-User-ID"))
    ):
        try:
            return CurrentUser(id=UUID(header_user_id))
        except ValueError as exc:
            raise AppError("AUTHENTICATION_REQUIRED", "Please sign in.", 401) from exc

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AppError("AUTHENTICATION_REQUIRED", "Please sign in.", 401)
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    require_csrf = request.method not in {"GET", "HEAD", "OPTIONS"}
    if require_csrf and (not csrf_header or csrf_header != csrf_cookie):
        raise AppError("CSRF_VALIDATION_FAILED", "The security token is invalid.", 403)

    identity = SessionService(session, settings).authenticate(
        token,
        csrf_token=csrf_header,
        require_csrf=require_csrf,
        enforce_privileged_mfa=enforce_privileged_mfa,
    )
    return CurrentUser(
        id=identity.user_id,
        role=identity.role,
        plan=identity.plan,
        session_id=identity.session_id,
    )


def current_user(request: Request, session: DbSession) -> CurrentUser:
    return _resolve_current_user(request, session, enforce_privileged_mfa=False)


def mfa_setup_user(request: Request, session: DbSession) -> CurrentUser:
    return _resolve_current_user(request, session, enforce_privileged_mfa=False)
