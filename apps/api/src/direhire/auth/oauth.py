import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Depends

from direhire.config import Settings, get_settings
from direhire.errors import AppError


@dataclass(frozen=True, slots=True)
class AuthorizationFlow:
    authorization_url: str
    state: str
    nonce: str
    code_verifier: str


@dataclass(frozen=True, slots=True)
class CognitoIdentity:
    subject: str
    email: str
    email_verified: bool


class CognitoOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def begin_authorization(self) -> AuthorizationFlow:
        domain, _, client_id, redirect_uri = self._required_config()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationFlow(
            authorization_url=f"{domain.rstrip('/')}/oauth2/authorize?{query}",
            state=state,
            nonce=nonce,
            code_verifier=verifier,
        )

    def complete_authorization(
        self, *, code: str, code_verifier: str, nonce: str
    ) -> CognitoIdentity:
        domain, user_pool_id, client_id, redirect_uri = self._required_config()
        try:
            response = httpx.post(
                f"{domain.rstrip('/')}/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            response.raise_for_status()
            id_token = response.json()["id_token"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise AppError(
                "AUTH_PROVIDER_UNAVAILABLE",
                "Sign-in could not be completed. Please try again.",
                503,
                retryable=True,
            ) from exc

        issuer = f"https://cognito-idp.{user_pool_id.split('_', 1)[0]}.amazonaws.com/{user_pool_id}"
        jwks_url = f"{issuer}/.well-known/jwks.json"
        try:
            signing_key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=client_id,
                issuer=issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce", "token_use"]},
            )
        except jwt.PyJWTError as exc:
            raise AppError("AUTH_TOKEN_INVALID", "Sign-in could not be verified.", 401) from exc

        if claims.get("token_use") != "id" or not secrets.compare_digest(
            str(claims.get("nonce", "")), nonce
        ):
            raise AppError("AUTH_TOKEN_INVALID", "Sign-in could not be verified.", 401)
        email = claims.get("email")
        if not isinstance(email, str) or claims.get("email_verified") is not True:
            raise AppError("EMAIL_NOT_VERIFIED", "Verify your email before signing in.", 403)
        return CognitoIdentity(subject=str(claims["sub"]), email=email, email_verified=True)

    def _required_config(self) -> tuple[str, str, str, str]:
        values = (
            self.settings.cognito_domain,
            self.settings.cognito_user_pool_id,
            self.settings.cognito_client_id,
            self.settings.cognito_redirect_uri,
        )
        if not all(values):
            raise AppError(
                "AUTH_NOT_CONFIGURED",
                "Sign-in is not configured for this environment.",
                503,
            )
        return values  # type: ignore[return-value]


def get_cognito_client(settings: Annotated[Settings, Depends(get_settings)]) -> CognitoOAuthClient:
    return CognitoOAuthClient(settings)
