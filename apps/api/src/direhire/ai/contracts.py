from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JOB_DEMAND_SCHEMA_VERSION = 2
JOB_ANALYSIS_PROMPT_VERSION = "jd-holistic-v2"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Evidence & Confidence Enums/Types
EvidenceStrength = Literal["EXPLICIT", "STRONGLY_IMPLIED", "INFERRED"]
InterpretationConfidence = Literal["HIGH", "MEDIUM", "LOW"]


class EvidenceItemV2(StrictModel):
    value: str = Field(min_length=1, max_length=500, description="English synthesis/value")
    evidence: str = Field(
        min_length=1,
        max_length=600,
        description="Exact quote/paraphrase in original language (e.g. Thai)",
    )
    evidence_strength: EvidenceStrength
    interpretation_confidence: InterpretationConfidence


class RoleReality(StrictModel):
    headline: str = Field(
        min_length=1,
        max_length=300,
        description="One-sentence summary of actual operational reality",
    )
    primary_archetype: str = Field(
        min_length=1,
        max_length=160,
        description="Operational role archetype, e.g. HANDS_ON_IT_GENERALIST",
    )
    primary_occupation: str = Field(min_length=1, max_length=160)
    secondary_occupations: list[str] = Field(default_factory=list, max_length=10)
    title_alignment: Literal["ACCURATE", "UNDERSTATES_SCOPE", "OVERSTATES_SCOPE", "MISLEADING"]
    primary_mission: str = Field(min_length=1, max_length=500)
    breadth: Literal["SPECIALIZED", "MODERATE", "BROAD"]


class SeniorityAssessment(StrictModel):
    assessment: Literal[
        "ENTRY",
        "EARLY_CAREER_TO_MID",
        "MID",
        "MID_TO_SENIOR",
        "SENIOR",
        "LEAD",
        "EXECUTIVE",
        "UNCLEAR",
    ]
    explicit_min_years: float | None = Field(default=None, ge=0, le=40)
    explicit_max_years: float | None = Field(default=None, ge=0, le=40)
    interpretation_confidence: InterpretationConfidence
    reason: str = Field(min_length=1, max_length=500)


class DemandCluster(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    priority: Literal["CORE", "IMPORTANT", "SUPPORTING", "PREFERRED"]
    reason: str = Field(min_length=1, max_length=400)
    evidence: str = Field(
        min_length=1,
        max_length=500,
        description="Exact quote in original language",
    )
    evidence_strength: EvidenceStrength


class RequirementCategory(StrictModel):
    category: Literal["ELIGIBILITY", "CAPABILITY", "PROFESSIONAL", "PREFERRED"]
    title: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=1, max_length=500)
    evidence_strength: EvidenceStrength


class JobConstraint(StrictModel):
    constraint_type: Literal[
        "LOCATION", "SCHEDULE", "WORK_ARRANGEMENT", "TRAVEL", "LICENSE", "OTHER"
    ]
    description: str = Field(min_length=1, max_length=300)
    evidence_strength: EvidenceStrength


class CompetencyDemandV2(StrictModel):
    canonical_id: str | None = Field(default=None, max_length=100)
    display_name: str = Field(min_length=1, max_length=160)
    category: Literal["TECHNICAL", "OPERATIONAL", "PROFESSIONAL", "TOOLS"]
    priority: Literal["CORE", "IMPORTANT", "SUPPORTING", "PREFERRED"]
    evidence: str = Field(min_length=1, max_length=500)
    evidence_strength: EvidenceStrength


class JobDemandProfileContent(StrictModel):
    role_summary: str = Field(min_length=1, max_length=1200)
    role_reality: RoleReality
    seniority: SeniorityAssessment
    demand_clusters: list[DemandCluster] = Field(min_length=1, max_length=20)
    competencies: list[CompetencyDemandV2] = Field(max_length=40)
    responsibility_clusters: list[EvidenceItemV2] = Field(max_length=20)
    requirements: list[RequirementCategory] = Field(max_length=30)
    job_constraints: list[JobConstraint] = Field(max_length=20)
    work_location_summary: EvidenceItemV2
    work_arrangement_summary: EvidenceItemV2
    remote_eligibility: Literal["NOT_REMOTE", "LOCATION_RESTRICTED", "WORLDWIDE", "UNCLEAR"]
    real_work_scenarios: list[str] = Field(min_length=1, max_length=12)
    contradictions: list[str] = Field(max_length=12)
    overall_confidence: InterpretationConfidence


# Legacy aliases for backward compatibility where referenced
EvidenceItem = EvidenceItemV2
CompetencyDemand = CompetencyDemandV2


class AnalysisProvenance(StrictModel):
    schema_version: int
    prompt_version: str
    provider: str
    route_key: str
    model: str
    input_hash: str
    generated_at: datetime


class JobDemandProfileDocument(StrictModel):
    job_version_id: str
    content: JobDemandProfileContent
    provenance: AnalysisProvenance
