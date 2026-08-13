from uuid import uuid4

import pytest
from direhire.models import AuditEvent, User
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from scripts.bootstrap_superadmin import promote


class FakeCognitoAdmin:
    def __init__(self, *, mfa_enabled: bool) -> None:
        self.mfa_enabled = mfa_enabled

    def admin_get_user(self, *, UserPoolId: str, Username: str) -> dict[str, object]:
        assert UserPoolId == "pool-id"
        assert Username == "subject-1"
        return {
            "Username": Username,
            "Enabled": True,
            "UserStatus": "CONFIRMED",
            "UserMFASettingList": ["SOFTWARE_TOKEN_MFA"] if self.mfa_enabled else [],
        }


def test_bootstrap_requires_verified_mfa_and_records_append_only_audit(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        user = User(id=str(uuid4()), cognito_subject="subject-1", email="owner@example.invalid")
        database.add(user)
        database.commit()

        with pytest.raises(RuntimeError, match="enroll and verify TOTP"):
            promote(
                database,
                FakeCognitoAdmin(mfa_enabled=False),
                user_pool_id="pool-id",
                cognito_subject="subject-1",
            )

        promoted = promote(
            database,
            FakeCognitoAdmin(mfa_enabled=True),
            user_pool_id="pool-id",
            cognito_subject="subject-1",
        )
        assert promoted.role == "SUPERADMIN"
        assert promoted.mfa_enabled is True
        assert promoted.security_version == 2
        audit = database.scalar(select(AuditEvent))
        assert audit is not None
        assert audit.action == "INITIAL_SUPERADMIN_BOOTSTRAPPED"
        assert audit.actor_role == "SYSTEM"
        assert audit.change_metadata["after"] == {
            "role": "SUPERADMIN",
            "mfa_enabled": True,
        }
