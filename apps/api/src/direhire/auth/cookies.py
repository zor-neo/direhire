from fastapi import Response

from direhire.auth.session_service import IssuedSession
from direhire.config import Settings


def set_session_cookies(response: Response, issued: IssuedSession, settings: Settings) -> None:
    secure = settings.environment == "production"
    max_age = settings.session_lifetime_seconds
    response.set_cookie(
        settings.session_cookie_name,
        issued.token,
        max_age=max_age,
        expires=issued.expires_at,
        secure=secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        issued.csrf_token,
        max_age=max_age,
        expires=issued.expires_at,
        secure=secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    secure = settings.environment == "production"
    response.delete_cookie(
        settings.session_cookie_name, secure=secure, httponly=True, samesite="lax"
    )
    response.delete_cookie(settings.csrf_cookie_name, secure=secure, httponly=False, samesite="lax")
