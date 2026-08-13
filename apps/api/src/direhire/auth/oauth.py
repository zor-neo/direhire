import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Annotated, Literal, Protocol
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
    mfa_enabled: bool = False
    access_token: str | None = field(default=None, repr=False)


class CognitoUserClient(Protocol):
    def get_user(self, *, AccessToken: str) -> dict[str, object]: ...

    def associate_software_token(self, *, AccessToken: str) -> dict[str, object]: ...

    def verify_software_token(
        self, *, AccessToken: str, UserCode: str, FriendlyDeviceName: str
    ) -> dict[str, object]: ...

    def set_user_mfa_preference(
        self, *, AccessToken: str, SoftwareTokenMfaSettings: dict[str, bool]
    ) -> dict[str, object]: ...


class CognitoOAuthClient:
    def __init__(self, settings: Settings, user_client: CognitoUserClient | None = None) -> None:
        self.settings = settings
        self._user_client = user_client

    def begin_authorization(
        self, *, screen: Literal["login", "signup"] = "login"
    ) -> AuthorizationFlow:
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
                "scope": "openid email aws.cognito.signin.user.admin",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        authorization_path = "signup" if screen == "signup" else "oauth2/authorize"
        return AuthorizationFlow(
            authorization_url=f"{domain.rstrip('/')}/{authorization_path}?{query}",
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
            token_body = response.json()
            id_token = token_body["id_token"]
            access_token = token_body["access_token"]
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
        try:
            cognito_user = self._client().get_user(AccessToken=access_token)
            mfa_settings = cognito_user.get("UserMFASettingList", [])
            mfa_enabled = "SOFTWARE_TOKEN_MFA" in mfa_settings
        except Exception as exc:
            raise AppError(
                "AUTH_PROVIDER_UNAVAILABLE",
                "Sign-in could not be completed. Please try again.",
                503,
                retryable=True,
            ) from exc
        return CognitoIdentity(
            subject=str(claims["sub"]),
            email=email,
            email_verified=True,
            mfa_enabled=mfa_enabled,
            access_token=access_token,
        )

    def begin_mfa_setup(self, access_token: str) -> str:
        try:
            response = self._client().associate_software_token(AccessToken=access_token)
            return str(response["SecretCode"])
        except Exception as exc:
            raise AppError(
                "MFA_SETUP_FAILED", "MFA setup could not be started.", 503, True
            ) from exc

    def complete_mfa_setup(self, access_token: str, code: str) -> None:
        try:
            verified = self._client().verify_software_token(
                AccessToken=access_token,
                UserCode=code,
                FriendlyDeviceName="DireHire",
            )
            if verified.get("Status") != "SUCCESS":
                raise ValueError("TOTP verification did not succeed")
            self._client().set_user_mfa_preference(
                AccessToken=access_token,
                SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
            )
        except Exception as exc:
            raise AppError("MFA_CODE_INVALID", "The authenticator code is invalid.", 400) from exc

    def _client(self) -> CognitoUserClient:
        if self._user_client is None:
            import boto3

            self._user_client = boto3.client("cognito-idp")
        return self._user_client

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
