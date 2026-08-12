import json

from direhire.workers import runtime


def test_runtime_routes_supported_event_and_reports_only_failed_item(monkeypatch) -> None:
    processed: list[str] = []
    monkeypatch.setitem(
        runtime.PROCESSORS,
        "test.event",
        ("test-workload", lambda envelope: processed.append(envelope.event_id)),
    )
    valid = {
        "event_id": "evt_1",
        "event_type": "test.event",
        "schema_version": 1,
        "occurred_at": "2026-08-12T00:00:00Z",
        "correlation_id": "cor_1",
        "payload": {},
    }
    event = {
        "Records": [
            {"messageId": "ok", "body": json.dumps(valid)},
            {"messageId": "wrong", "body": json.dumps({**valid, "event_id": "evt_2"})},
        ]
    }
    result = runtime.handle_sqs_batch(event, workload="test-workload")
    assert result == {"batchItemFailures": []}
    assert processed == ["evt_1", "evt_2"]


def test_runtime_rejects_event_on_wrong_queue(monkeypatch) -> None:
    monkeypatch.setitem(runtime.PROCESSORS, "test.event", ("expected", lambda envelope: None))
    body = json.dumps(
        {
            "event_id": "evt_1",
            "event_type": "test.event",
            "schema_version": 1,
            "occurred_at": "2026-08-12T00:00:00Z",
            "correlation_id": "cor_1",
            "payload": {},
        }
    )
    result = runtime.handle_sqs_batch(
        {"Records": [{"messageId": "bad", "body": body}]}, workload="other"
    )
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
