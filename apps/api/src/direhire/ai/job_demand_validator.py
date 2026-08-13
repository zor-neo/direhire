import html
import unicodedata

from direhire.ai.contracts import JobDemandProfileContent


def validate_job_demand_profile(content: JobDemandProfileContent, source_text: str) -> list[str]:
    """Validate post-Pydantic business invariants for JobDemandProfileContent V2.

    Pydantic checks structural validity; this function checks logical defensibility
    against the source text and domain business rules.

    Returns a list of error string violations (empty list = valid).
    """
    errors: list[str] = []
    normalized_source = _normalize_text(source_text)

    # Rule 1: Evidence Grounding Invariant
    for i, cluster in enumerate(content.demand_clusters):
        if cluster.evidence_strength == "EXPLICIT":
            if not cluster.evidence or not cluster.evidence.strip():
                errors.append(f"demand_clusters[{i}].evidence is empty for EXPLICIT strength")
            elif not _is_evidence_grounded(cluster.evidence, normalized_source):
                errors.append(
                    f"demand_clusters[{i}].evidence missing from source: '{cluster.evidence[:30]}'"
                )

    for i, req in enumerate(content.requirements):
        if req.evidence_strength == "EXPLICIT":
            if not req.evidence or not req.evidence.strip():
                errors.append(f"requirements[{i}].evidence is empty for EXPLICIT strength")
            elif not _is_evidence_grounded(req.evidence, normalized_source):
                errors.append(
                    f"requirements[{i}].evidence '{req.evidence[:40]}...' not found in source text"
                )

    # Rule 2: Seniority Grounding Check
    if (
        content.seniority.assessment in ("SENIOR", "LEAD", "EXECUTIVE")
        and content.seniority.explicit_min_years is None
        and content.seniority.interpretation_confidence == "LOW"
    ):
        errors.append(
            f"Seniority assessment '{content.seniority.assessment}' has no explicit min years"
        )

    # Rule 3: Remote Eligibility Invariant
    # NOT_REMOTE requires explicit on-site work-arrangement phrases; address alone is insufficient
    if content.remote_eligibility == "NOT_REMOTE":
        explicit_onsite_phrases = (
            "on-site only",
            "work on-site",
            "work on site",
            "no remote work",
            "must work at",
            "ประจำสำนักงาน",
            "ทำงานที่",
            "ปฏิบัติงาน ณ สำนักงาน",
            "on-site workplace",
            "physical presence",
        )
        if not any(phrase in normalized_source for phrase in explicit_onsite_phrases):
            errors.append(
                "remote_eligibility marked NOT_REMOTE without explicit on-site evidence"
            )

    # WORLDWIDE requires explicit worldwide or work anywhere language in source text
    if content.remote_eligibility == "WORLDWIDE":
        worldwide_keywords = ("worldwide", "anywhere", "work from anywhere", "global remote")
        if not any(k in normalized_source for k in worldwide_keywords):
            errors.append("remote_eligibility marked WORLDWIDE without explicit worldwide evidence")

    return errors


def _normalize_text(text: str) -> str:
    """Normalize text for evidence grounding comparison.

    1. Unescape HTML entities
    2. Apply Unicode NFKC normalization
    3. Convert to lowercase
    4. Collapse non-breaking spaces and whitespace
    """
    unescaped = html.unescape(text)
    nfkc_norm = unicodedata.normalize("NFKC", unescaped)
    clean_ws = " ".join(nfkc_norm.lower().split())
    return clean_ws


def _is_evidence_grounded(evidence: str, normalized_source: str) -> bool:
    """Check if evidence quote is grounded in normalized_source text."""
    clean_ev = _normalize_text(evidence)
    if clean_ev in normalized_source:
        return True
    # Token overlap fallback for multiline or paraphrased formatting
    tokens = [t for t in clean_ev.split() if len(t) > 1]
    if not tokens:
        return True
    matches = sum(1 for t in tokens if t in normalized_source)
    return (matches / len(tokens)) >= 0.75
