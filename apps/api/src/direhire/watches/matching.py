from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchResult:
    matched: bool
    target_hits: tuple[str, ...]
    missing_required: tuple[str, ...]
    excluded_hits: tuple[str, ...]


def deterministic_match(
    *, text: str, target_terms: list[str], required_terms: list[str], excluded_terms: list[str]
) -> MatchResult:
    """Target broadens, Required is mandatory, and Exclude filters."""
    haystack = " ".join(text.casefold().split())
    target_hits = tuple(term for term in target_terms if term.casefold() in haystack)
    missing_required = tuple(term for term in required_terms if term.casefold() not in haystack)
    excluded_hits = tuple(term for term in excluded_terms if term.casefold() in haystack)
    return MatchResult(
        matched=bool(target_hits) and not missing_required and not excluded_hits,
        target_hits=target_hits,
        missing_required=missing_required,
        excluded_hits=excluded_hits,
    )
