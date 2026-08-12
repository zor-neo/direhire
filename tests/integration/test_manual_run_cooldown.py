from direhire.models import JobWatchRun, PlanEntitlement
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker


def test_manual_run_cooldown_is_distinct_from_daily_quota(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as database:
        database.add_all(
            (
                PlanEntitlement(
                    plan="FREE",
                    entitlement_key="manual_runs_per_day",
                    enabled=True,
                    limit_value=10,
                ),
                PlanEntitlement(
                    plan="FREE",
                    entitlement_key="manual_run_cooldown_seconds",
                    enabled=True,
                    limit_value=3600,
                ),
            )
        )
        database.commit()
    watch = client.post(
        "/api/v1/watches", json={"name": "Cooldown", "target_terms": ["Python"]}
    ).json()
    assert client.post(f"/api/v1/watches/{watch['id']}/activate").status_code == 200
    first = client.post(f"/api/v1/watches/{watch['id']}/runs")
    assert first.status_code == 202
    with session_factory() as database:
        run = database.get(JobWatchRun, first.json()["id"])
        assert run is not None
        run.status = "SUCCEEDED"
        run.active_marker = None
        database.commit()

    limited = client.post(f"/api/v1/watches/{watch['id']}/runs")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.json()["error"]["retryable"] is True
