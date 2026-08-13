from direhire.ai.contracts import JobDemandProfileContent
from direhire.ai.job_demand_validator import validate_job_demand_profile


def test_validator_passes_well_grounded_profile() -> None:
    source_text = (
        "Qualifications: Require IT degree. "
        "Duties: Install LAN cables and RJ45 crimping. "
        "Workplace: Work on-site."
    )

    content = JobDemandProfileContent(
        role_summary="Hands-on IT support role",
        role_reality={
            "headline": "Internal IT generalist",
            "primary_archetype": "HANDS_ON_IT_GENERALIST",
            "primary_occupation": "IT Support Specialist",
            "secondary_occupations": [],
            "title_alignment": "ACCURATE",
            "primary_mission": "Maintain IT infrastructure",
            "breadth": "BROAD",
        },
        seniority={
            "assessment": "EARLY_CAREER_TO_MID",
            "explicit_min_years": 1.0,
            "explicit_max_years": 3.0,
            "interpretation_confidence": "HIGH",
            "reason": "Explicit IT experience request",
        },
        demand_clusters=[
            {
                "name": "Network & Cabling",
                "priority": "CORE",
                "reason": "Primary physical duty",
                "evidence": "Install LAN cables and RJ45 crimping",
                "evidence_strength": "EXPLICIT",
            }
        ],
        competencies=[],
        responsibility_clusters=[],
        requirements=[
            {
                "category": "ELIGIBILITY",
                "title": "Bachelor's degree in IT",
                "evidence": "Require IT degree",
                "evidence_strength": "EXPLICIT",
            }
        ],
        job_constraints=[],
        work_location_summary={
            "value": "Bangkok",
            "evidence": "Bangkok",
            "evidence_strength": "STRONGLY_IMPLIED",
            "interpretation_confidence": "HIGH",
        },
        work_arrangement_summary={
            "value": "On-site",
            "evidence": "On-site",
            "evidence_strength": "STRONGLY_IMPLIED",
            "interpretation_confidence": "HIGH",
        },
        remote_eligibility="NOT_REMOTE",
        real_work_scenarios=["Fix network connectivity"],
        contradictions=[],
        overall_confidence="HIGH",
    )

    errors = validate_job_demand_profile(content, source_text)
    assert errors == [], f"Expected 0 errors, got {errors}"


def test_validator_detects_ungrounded_explicit_evidence() -> None:
    source_text = "Qualifications: High school diploma required."

    content = JobDemandProfileContent(
        role_summary="Support role",
        role_reality={
            "headline": "Support role",
            "primary_archetype": "IT_SUPPORT",
            "primary_occupation": "IT Support",
            "secondary_occupations": [],
            "title_alignment": "ACCURATE",
            "primary_mission": "Support users",
            "breadth": "MODERATE",
        },
        seniority={
            "assessment": "ENTRY",
            "explicit_min_years": None,
            "explicit_max_years": None,
            "interpretation_confidence": "HIGH",
            "reason": "Entry level",
        },
        demand_clusters=[
            {
                "name": "Kubernetes cluster administration",
                "priority": "CORE",
                "reason": "Claimed core duty",
                "evidence": "Manage 500 node Kubernetes cluster",  # Not in source text!
                "evidence_strength": "EXPLICIT",
            }
        ],
        competencies=[],
        responsibility_clusters=[],
        requirements=[],
        job_constraints=[],
        work_location_summary={
            "value": "Bangkok",
            "evidence": "Bangkok",
            "evidence_strength": "STRONGLY_IMPLIED",
            "interpretation_confidence": "HIGH",
        },
        work_arrangement_summary={
            "value": "On-site",
            "evidence": "On-site",
            "evidence_strength": "STRONGLY_IMPLIED",
            "interpretation_confidence": "HIGH",
        },
        remote_eligibility="NOT_REMOTE",
        real_work_scenarios=["Manage cluster"],
        contradictions=[],
        overall_confidence="HIGH",
    )

    errors = validate_job_demand_profile(content, source_text)
    assert len(errors) > 0
    assert "demand_clusters[0].evidence missing" in errors[0]
