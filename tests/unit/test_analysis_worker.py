from datetime import UTC, datetime

from direhire.events.outbox import EventEnvelope
from direhire.workers.analysis import build_credentials, handle_sqs_batch


class FakeSecrets:
    def get(self, parameter_name: str) -> str:
        return f"secret-for:{parameter_name}"


class FakeSettings:
    gemini_project_a_parameter = "/test/a"
    gemini_project_b_parameter = "/test/b"
    gemini_project_c_parameter = "/test/c"


def test_analysis_worker_reports_only_failed_records() -> None:
    processed: list[str] = []

    def process(envelope: EventEnvelope) -> None:
        if envelope.payload["profile_id"] == "bad":
            raise RuntimeError("synthetic failure")
        processed.append(str(envelope.payload["profile_id"]))

    def body(profile_id: str) -> str:
        return EventEnvelope(
            event_id=f"evt-{profile_id}",
            event_type="job.analysis.requested",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            correlation_id="c" * 36,
            payload={"profile_id": profile_id},
        ).model_dump_json()

    result = handle_sqs_batch(
        {
            "Records": [
                {"messageId": "one", "body": body("good")},
                {"messageId": "two", "body": body("bad")},
            ]
        },
        process,
    )

    assert processed == ["good"]
    assert result == {"batchItemFailures": [{"itemIdentifier": "two"}]}


def test_analysis_worker_resolves_three_distinct_ssm_parameters() -> None:
    credentials = build_credentials(FakeSettings(), FakeSecrets())  # type: ignore[arg-type]

    assert [credential.route_key for credential in credentials] == [
        "project-a",
        "project-b",
        "project-c",
    ]
    assert len({credential.api_key for credential in credentials}) == 3
