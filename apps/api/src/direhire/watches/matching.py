import re
from dataclasses import dataclass

from direhire.watches.aliases import variants_for


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
    target_hits = tuple(term for term in target_terms if _matches_group(haystack, term))
    missing_required = tuple(term for term in required_terms if not _matches_group(haystack, term))
    excluded_hits = tuple(term for term in excluded_terms if _matches_group(haystack, term))
    return MatchResult(
        matched=bool(target_hits) and not missing_required and not excluded_hits,
        target_hits=target_hits,
        missing_required=missing_required,
        excluded_hits=excluded_hits,
    )


def _matches_group(haystack: str, term: str) -> bool:
    return any(_contains_term(haystack, variant) for variant in variants_for(term))


def _contains_term(haystack: str, term: str) -> bool:
    needle = " ".join(term.casefold().split())
    if not needle:
        return False
    return re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", haystack) is not None
