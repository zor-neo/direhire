from direhire.watches.matching import deterministic_match


def test_target_broadens_while_required_and_exclude_constrain() -> None:
    result = deterministic_match(
        text="Senior Python engineer building data APIs in Bangkok",
        target_terms=["Python", "Go"],
        required_terms=["APIs"],
        excluded_terms=["unpaid"],
    )
    assert result.matched is True
    assert result.target_hits == ("Python",)


def test_missing_required_never_matches() -> None:
    result = deterministic_match(
        text="Python developer",
        target_terms=["Python"],
        required_terms=["German"],
        excluded_terms=[],
    )
    assert result.matched is False
    assert result.missing_required == ("German",)


def test_exclusion_wins() -> None:
    result = deterministic_match(
        text="Remote Python internship",
        target_terms=["Python"],
        required_terms=[],
        excluded_terms=["internship"],
    )
    assert result.matched is False
    assert result.excluded_hits == ("internship",)


def test_reviewed_alias_matches_target_and_required_groups() -> None:
    result = deterministic_match(
        text="Build server-side Python services backed by Postgres.",
        target_terms=["Backend"],
        required_terms=["PostgreSQL"],
        excluded_terms=[],
    )

    assert result.matched is True
    assert result.target_hits == ("Backend",)
    assert result.missing_required == ()


def test_short_alias_uses_token_boundaries() -> None:
    result = deterministic_match(
        text="A good communicator working with Django.",
        target_terms=["Golang"],
        required_terms=[],
        excluded_terms=[],
    )

    assert result.matched is False


def test_excluded_alias_still_filters() -> None:
    result = deterministic_match(
        text="Maintain legacy MSSQL databases.",
        target_terms=["Database"],
        required_terms=[],
        excluded_terms=["Microsoft SQL Server"],
    )

    assert result.matched is False
    assert result.excluded_hits == ("Microsoft SQL Server",)
