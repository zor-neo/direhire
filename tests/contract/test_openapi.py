from direhire.main import app


def test_watch_contract_paths_and_version_prefix_are_stable() -> None:
    schema = app.openapi()
    assert schema["info"]["version"] == "0.1.0"
    assert "/api/v1/watches" in schema["paths"]
    assert "/api/v1/watches/{watch_id}/activate" in schema["paths"]
    assert "/api/v1/watches/{watch_id}/runs" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/callback" in schema["paths"]
    assert "/api/v1/auth/session" in schema["paths"]
