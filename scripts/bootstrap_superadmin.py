from __future__ import annotations

import argparse
import uuid
from typing import Protocol

import boto3
from direhire.audit.service import AuditService
from direhire.db import SessionLocal
from direhire.models import User
from sqlalchemy import select
from sqlalchemy.orm import Session


class CognitoAdminClient(Protocol):
    def admin_get_user(self, *, UserPoolId: str, Username: str) -> dict[str, object]: ...


def promote(
    session: Session,
    cognito: CognitoAdminClient,
    *,
    user_pool_id: str,
    cognito_subject: str,
    allow_pending_mfa: bool = False,
) -> User:
    provider_user = cognito.admin_get_user(
        UserPoolId=user_pool_id,
        Username=cognito_subject,
    )
    if provider_user.get("UserStatus") != "CONFIRMED" or provider_user.get("Enabled") is False:
        raise RuntimeError("The Cognito account must be enabled and confirmed.")
    mfa_enabled = "SOFTWARE_TOKEN_MFA" in provider_user.get("UserMFASettingList", [])
    if not mfa_enabled and not allow_pending_mfa:
        raise RuntimeError("The Cognito account must enroll and verify TOTP before promotion.")

    user = session.scalar(select(User).where(User.cognito_subject == cognito_subject))
    if user is None:
        raise RuntimeError("The account must complete one DireHire sign-in before promotion.")
    existing = session.scalar(select(User).where(User.role == "SUPERADMIN", User.id != user.id))
    if existing is not None:
        raise RuntimeError("A different Superadmin already exists; use the reviewed role workflow.")

    before = {"role": user.role, "mfa_enabled": user.mfa_enabled}
    user.role = "SUPERADMIN"
    user.mfa_enabled = mfa_enabled
    user.security_version += 1
    AuditService(session).record(
        actor_user_id=None,
        actor_role="SYSTEM",
        action="INITIAL_SUPERADMIN_BOOTSTRAPPED",
        target_type="USER",
        target_id=user.id,
        result="SUCCEEDED",
        correlation_id=str(uuid.uuid4()),
        change_metadata={
            "before": before,
            "after": {"role": user.role, "mfa_enabled": user.mfa_enabled},
        },
    )
    session.commit()
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the initial DireHire Superadmin")
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--cognito-subject", required=True)
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument(
        "--allow-pending-mfa",
        action="store_true",
        help="Grant the role before TOTP enrollment; privileged sessions remain blocked.",
    )
    args = parser.parse_args()
    with SessionLocal() as session:
        user = promote(
            session,
            boto3.client("cognito-idp", region_name=args.region),
            user_pool_id=args.user_pool_id,
            cognito_subject=args.cognito_subject,
            allow_pending_mfa=args.allow_pending_mfa,
        )
    print(f"Bootstrapped Superadmin user_id={user.id}; mfa_enabled={user.mfa_enabled}")


if __name__ == "__main__":
    main()
