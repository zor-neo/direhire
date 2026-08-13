import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.config import Settings
from direhire.errors import AppError
from direhire.models import AuthSession, User


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    user_id: uuid.UUID
    role: str
    plan: str
    session_id: uuid.UUID


class SessionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def issue(self, user: User, *, now: datetime | None = None) -> IssuedSession:
        issued_at = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = issued_at + timedelta(seconds=self.settings.session_lifetime_seconds)
        auth_session = AuthSession(
            token_hash=token_hash(token),
            csrf_token_hash=token_hash(csrf_token),
            user_id=user.id,
            created_at=issued_at,
            expires_at=expires_at,
            last_seen_at=issued_at,
            security_version=user.security_version,
        )
        self.session.add(auth_session)
        self.session.commit()
        return IssuedSession(token=token, csrf_token=csrf_token, expires_at=expires_at)

    def authenticate(
        self,
        token: str,
        *,
        csrf_token: str | None = None,
        require_csrf: bool = False,
        enforce_privileged_mfa: bool = True,
        now: datetime | None = None,
    ) -> SessionIdentity:
        current_time = now or datetime.now(UTC)
        statement = (
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == token_hash(token))
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            raise self._authentication_required()
        auth_session, user = row
        expires_at = self._as_utc(auth_session.expires_at)
        if auth_session.revoked_at is not None or expires_at <= current_time:
            raise self._authentication_required()
        if (
            user.account_status != "ACTIVE"
            or auth_session.security_version != user.security_version
        ):
            raise self._authentication_required()
        if enforce_privileged_mfa and user.role in {"ADMIN", "SUPERADMIN"} and not user.mfa_enabled:
            raise AppError("MFA_REQUIRED", "Multi-factor authentication is required.", 403)
        if require_csrf and (
            not csrf_token
            or not secrets.compare_digest(auth_session.csrf_token_hash, token_hash(csrf_token))
        ):
            raise AppError("CSRF_VALIDATION_FAILED", "The security token is invalid.", 403)

        last_seen_at = self._as_utc(auth_session.last_seen_at)
        interval = timedelta(seconds=self.settings.session_last_seen_interval_seconds)
        if current_time - last_seen_at >= interval:
            auth_session.last_seen_at = current_time
            self.session.commit()
        return SessionIdentity(
            user_id=uuid.UUID(user.id),
            role=user.role,
            plan=user.plan,
            session_id=uuid.UUID(auth_session.id),
        )

    def revoke(self, session_id: uuid.UUID, *, now: datetime | None = None) -> None:
        auth_session = self.session.get(AuthSession, str(session_id))
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = now or datetime.now(UTC)
            self.session.commit()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _authentication_required() -> AppError:
        return AppError("AUTHENTICATION_REQUIRED", "Please sign in.", 401)
