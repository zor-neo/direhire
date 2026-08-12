import argparse
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from direhire.config import get_settings  # noqa: E402
from direhire.db import SessionLocal  # noqa: E402
from direhire.models import JobWatch, User  # noqa: E402

SYNTHETIC_USER_ID = UUID("11111111-1111-4111-8111-111111111111")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic local DireHire demo data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove and recreate only the deterministic synthetic user's records.",
    )
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("Synthetic seed data is forbidden in production.")

    owner_id = str(SYNTHETIC_USER_ID)
    with SessionLocal.begin() as session:
        if args.reset:
            session.execute(delete(JobWatch).where(JobWatch.owner_id == owner_id))
            session.execute(delete(User).where(User.id == owner_id))
        user = session.scalar(select(User).where(User.id == owner_id))
        if user is None:
            session.add(
                User(
                    id=owner_id,
                    cognito_subject="synthetic-local-user",
                    email="alex.rivera@example.invalid",
                    role="USER",
                    plan="FREE",
                )
            )
        watch = session.scalar(
            select(JobWatch).where(
                JobWatch.owner_id == owner_id,
                JobWatch.name == "SEA backend roles",
            )
        )
        if watch is None:
            session.add(
                JobWatch(
                    id="33333333-3333-4333-8333-333333333333",
                    owner_id=owner_id,
                    name="SEA backend roles",
                    status="DRAFT",
                    target_terms=["Python", "FastAPI", "Backend Engineer"],
                    required_terms=["PostgreSQL"],
                    excluded_terms=["Unpaid"],
                    locations=["Bangkok", "Singapore", "Remote"],
                    raw_intent="Backend roles in Southeast Asia using Python and PostgreSQL.",
                    posting_age_days=30,
                )
            )


if __name__ == "__main__":
    main()
