import secrets
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from direhire.audit.service import ActivityService
from direhire.auth.cookies import clear_session_cookies, set_session_cookies
from direhire.auth.dependencies import CurrentUser, current_user, mfa_setup_user
from direhire.auth.oauth import CognitoOAuthClient, get_cognito_client
from direhire.auth.schemas import MfaSetupRead, MfaVerifyRequest, SessionRead
from direhire.auth.session_service import SessionService
from direhire.auth.user_service import UserService
from direhire.config import get_settings
from direhire.db import get_session
from direhire.errors import AppError
from direhire.models import User as UserModel

router = APIRouter(prefix="/auth", tags=["Authentication"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
MfaUser = Annotated[CurrentUser, Depends(mfa_setup_user)]
CognitoClient = Annotated[CognitoOAuthClient, Depends(get_cognito_client)]

OAUTH_COOKIE_MAX_AGE = 10 * 60


def _begin_auth(
    client: CognitoOAuthClient, *, signup: bool, purpose: str = "login"
) -> RedirectResponse:
    settings = get_settings()
    flow = client.begin_authorization(screen="signup" if signup else "login")
    response = RedirectResponse(flow.authorization_url)
    secure = settings.environment == "production"
    for name, value in (
        ("direhire_oauth_state", flow.state),
        ("direhire_oidc_nonce", flow.nonce),
        ("direhire_pkce_verifier", flow.code_verifier),
        ("direhire_auth_purpose", purpose),
    ):
        response.set_cookie(
            name,
            value,
            max_age=OAUTH_COOKIE_MAX_AGE,
            secure=secure,
            httponly=True,
            samesite="lax",
            path="/api/v1/auth",
        )
    return response


@router.get("/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def begin_login(client: CognitoClient) -> RedirectResponse:
    return _begin_auth(client, signup=False)


@router.get("/signup", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def begin_signup(client: CognitoClient) -> RedirectResponse:
    return _begin_auth(client, signup=True)


@router.get("/mfa/setup", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def start_mfa_setup(client: CognitoClient, user: MfaUser) -> RedirectResponse:
    del user
    return _begin_auth(client, signup=False, purpose="mfa_setup")


@router.get("/callback", status_code=status.HTTP_303_SEE_OTHER)
def complete_login(
    request: Request,
    client: CognitoClient,
    session: DbSession,
    code: Annotated[str, Query(min_length=1, max_length=4096)],
    state: Annotated[str, Query(min_length=1, max_length=512)],
    oauth_state: Annotated[str | None, Cookie(alias="direhire_oauth_state")] = None,
    oidc_nonce: Annotated[str | None, Cookie(alias="direhire_oidc_nonce")] = None,
    code_verifier: Annotated[str | None, Cookie(alias="direhire_pkce_verifier")] = None,
    auth_purpose: Annotated[str | None, Cookie(alias="direhire_auth_purpose")] = None,
) -> RedirectResponse:
    if not oauth_state or not secrets.compare_digest(state, oauth_state):
        raise AppError("AUTH_STATE_INVALID", "Sign-in could not be verified.", 401)
    if not oidc_nonce or not code_verifier:
        raise AppError("AUTH_FLOW_EXPIRED", "Sign-in expired. Please try again.", 401)

    identity = client.complete_authorization(
        code=code,
        code_verifier=code_verifier,
        nonce=oidc_nonce,
    )
    user = UserService(session).find_or_create_from_cognito(identity)
    if auth_purpose == "mfa_setup":
        current = mfa_setup_user(request, session)
        if str(current.id) != user.id or not identity.access_token:
            raise AppError("MFA_SETUP_IDENTITY_MISMATCH", "MFA setup could not be verified.", 403)
        secret_code = client.begin_mfa_setup(identity.access_token)
        frontend = urlsplit(get_settings().frontend_post_login_url)
        response = RedirectResponse(
            f"{frontend.scheme}://{frontend.netloc}/settings/?mfa=setup", status_code=303
        )
        _set_mfa_cookie(response, "direhire_mfa_access", identity.access_token)
        _set_mfa_cookie(response, "direhire_mfa_secret", secret_code)
        _clear_oauth_cookies(response)
        return response
    ActivityService(session).record(user.id, "SIGNED_IN")
    issued = SessionService(session, get_settings()).issue(user)
    response = RedirectResponse(get_settings().frontend_post_login_url, status_code=303)
    set_session_cookies(response, issued, get_settings())
    _clear_oauth_cookies(response)
    return response


def _set_mfa_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=OAUTH_COOKIE_MAX_AGE,
        secure=get_settings().environment == "production",
        httponly=True,
        samesite="lax",
        path="/api/v1/auth/mfa",
    )


def _clear_oauth_cookies(response: Response) -> None:
    for name in (
        "direhire_oauth_state",
        "direhire_oidc_nonce",
        "direhire_pkce_verifier",
        "direhire_auth_purpose",
    ):
        response.delete_cookie(name, path="/api/v1/auth")


def _clear_mfa_cookies(response: Response) -> None:
    for name in ("direhire_mfa_access", "direhire_mfa_secret"):
        response.delete_cookie(name, path="/api/v1/auth/mfa")


@router.get("/mfa/setup-details", response_model=MfaSetupRead)
def read_mfa_setup(
    session: DbSession,
    user: MfaUser,
    secret_code: Annotated[str | None, Cookie(alias="direhire_mfa_secret")] = None,
) -> MfaSetupRead:
    if not secret_code:
        raise AppError("MFA_SETUP_EXPIRED", "MFA setup expired. Please start again.", 401)
    account = session.get(UserModel, str(user.id))
    if account is None:
        raise AppError("AUTHENTICATION_REQUIRED", "Please sign in.", 401)
    return MfaSetupRead(secret_code=secret_code, account_name=account.email)


@router.post("/mfa/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify_mfa_setup(
    data: MfaVerifyRequest,
    response: Response,
    client: CognitoClient,
    session: DbSession,
    user: MfaUser,
    access_token: Annotated[str | None, Cookie(alias="direhire_mfa_access")] = None,
) -> None:
    if not access_token:
        raise AppError("MFA_SETUP_EXPIRED", "MFA setup expired. Please start again.", 401)
    client.complete_mfa_setup(access_token, data.code)
    account = session.get(UserModel, str(user.id))
    if account is None:
        raise AppError("AUTHENTICATION_REQUIRED", "Please sign in.", 401)
    account.mfa_enabled = True
    account.security_version += 1
    ActivityService(session).record(account.id, "MFA_ENABLED")
    session.commit()
    _clear_mfa_cookies(response)


@router.get("/csrf-token")
def csrf_token(request: Request, response: Response, user: User) -> dict[str, str]:
    del user
    token = request.cookies.get(get_settings().csrf_cookie_name)
    if not token:
        raise AppError("CSRF_TOKEN_MISSING", "The security token is unavailable.", 401)
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.get("/session", response_model=SessionRead)
def read_current_session(response: Response, user: User) -> SessionRead:
    response.headers["Cache-Control"] = "no-store"
    return SessionRead(role=user.role, plan=user.plan)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def revoke_current_session(response: Response, user: User, session: DbSession) -> None:
    if user.session_id is not None:
        ActivityService(session).record(str(user.id), "SIGNED_OUT")
        SessionService(session, get_settings()).revoke(user.session_id)
    clear_session_cookies(response, get_settings())
