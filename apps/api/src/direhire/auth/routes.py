import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from direhire.audit.service import ActivityService
from direhire.auth.cookies import clear_session_cookies, set_session_cookies
from direhire.auth.dependencies import CurrentUser, current_user
from direhire.auth.oauth import CognitoOAuthClient, get_cognito_client
from direhire.auth.session_service import SessionService
from direhire.auth.user_service import UserService
from direhire.config import get_settings
from direhire.db import get_session
from direhire.errors import AppError

router = APIRouter(prefix="/auth", tags=["Authentication"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
CognitoClient = Annotated[CognitoOAuthClient, Depends(get_cognito_client)]

OAUTH_COOKIE_MAX_AGE = 10 * 60


@router.get("/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def begin_login(client: CognitoClient) -> RedirectResponse:
    settings = get_settings()
    flow = client.begin_authorization()
    response = RedirectResponse(flow.authorization_url)
    secure = settings.environment == "production"
    for name, value in (
        ("direhire_oauth_state", flow.state),
        ("direhire_oidc_nonce", flow.nonce),
        ("direhire_pkce_verifier", flow.code_verifier),
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


@router.get("/callback", status_code=status.HTTP_303_SEE_OTHER)
def complete_login(
    client: CognitoClient,
    session: DbSession,
    code: Annotated[str, Query(min_length=1, max_length=4096)],
    state: Annotated[str, Query(min_length=1, max_length=512)],
    oauth_state: Annotated[str | None, Cookie(alias="direhire_oauth_state")] = None,
    oidc_nonce: Annotated[str | None, Cookie(alias="direhire_oidc_nonce")] = None,
    code_verifier: Annotated[str | None, Cookie(alias="direhire_pkce_verifier")] = None,
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
    ActivityService(session).record(user.id, "SIGNED_IN")
    issued = SessionService(session, get_settings()).issue(user)
    response = RedirectResponse(get_settings().frontend_post_login_url, status_code=303)
    set_session_cookies(response, issued, get_settings())
    for name in ("direhire_oauth_state", "direhire_oidc_nonce", "direhire_pkce_verifier"):
        response.delete_cookie(name, path="/api/v1/auth")
    return response


@router.get("/csrf-token")
def csrf_token(request: Request, response: Response, user: User) -> dict[str, str]:
    del user
    token = request.cookies.get(get_settings().csrf_cookie_name)
    if not token:
        raise AppError("CSRF_TOKEN_MISSING", "The security token is unavailable.", 401)
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def revoke_current_session(response: Response, user: User, session: DbSession) -> None:
    if user.session_id is not None:
        ActivityService(session).record(str(user.id), "SIGNED_OUT")
        SessionService(session, get_settings()).revoke(user.session_id)
    clear_session_cookies(response, get_settings())
