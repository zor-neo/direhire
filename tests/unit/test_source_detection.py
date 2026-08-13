from direhire.sources.detection import resolve_custom_source


def test_detects_and_transforms_supported_careers_urls() -> None:
    assert resolve_custom_source("https://boards.greenhouse.io/fictional") == (
        "greenhouse",
        "https://boards-api.greenhouse.io/v1/boards/fictional/jobs?content=true",
    )
    assert resolve_custom_source("https://jobs.lever.co/fictional") == (
        "lever",
        "https://api.lever.co/v0/postings/fictional?mode=json",
    )
    assert resolve_custom_source("https://fictional.recruitee.com/careers") == (
        "recruitee",
        "https://fictional.recruitee.com/api/offers",
    )
    assert resolve_custom_source("https://apply.workable.com/fictional/") == (
        "workable",
        "https://apply.workable.com/api/v1/widget/accounts/fictional?details=true",
    )
    assert resolve_custom_source(
        "https://apply.workable.com/api/v1/widget/accounts/fictional"
    ) == (
        "workable",
        "https://apply.workable.com/api/v1/widget/accounts/fictional?details=true",
    )


def test_unknown_public_url_uses_generic_adapter() -> None:
    assert resolve_custom_source("https://careers.example.com/jobs") == (
        "generic_public",
        "https://careers.example.com/jobs",
    )
