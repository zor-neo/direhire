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
