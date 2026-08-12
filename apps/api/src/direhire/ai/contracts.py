from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JOB_DEMAND_SCHEMA_VERSION = 1
JOB_ANALYSIS_PROMPT_VERSION = "jd-holistic-v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceItem(StrictModel):
    value: str = Field(min_length=1, max_length=300)
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class CompetencyDemand(StrictModel):
    canonical_id: str | None = Field(default=None, max_length=100)
    display_name: str = Field(min_length=1, max_length=160)
    proficiency_demand: int = Field(ge=1, le=5)
    importance: int = Field(ge=1, le=3)
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class JobDemandProfileContent(StrictModel):
    role_summary: str = Field(min_length=1, max_length=1200)
    role_family: str | None = Field(default=None, max_length=160)
    normalized_occupation: str | None = Field(default=None, max_length=160)
    seniority: Literal["ENTRY", "MID", "SENIOR", "LEAD", "EXECUTIVE", "UNCLEAR"]
    responsibility_areas: list[EvidenceItem] = Field(max_length=20)
    competencies: list[CompetencyDemand] = Field(max_length=40)
    languages: list[EvidenceItem] = Field(max_length=15)
    education: list[EvidenceItem] = Field(max_length=15)
    experience: list[EvidenceItem] = Field(max_length=20)
    credentials_licenses: list[EvidenceItem] = Field(max_length=15)
    schedule_availability: list[EvidenceItem] = Field(max_length=15)
    work_conditions: list[EvidenceItem] = Field(max_length=15)
    employment_type: str | None = Field(default=None, max_length=100)
    work_arrangement: str | None = Field(default=None, max_length=100)
    remote_eligibility: Literal["NOT_REMOTE", "LOCATION_RESTRICTED", "WORLDWIDE", "UNCLEAR"]
    hard_requirements: list[EvidenceItem] = Field(max_length=30)
    preferred_requirements: list[EvidenceItem] = Field(max_length=30)
    possible_blockers: list[EvidenceItem] = Field(max_length=20)
    real_work_scenarios: list[str] = Field(max_length=12)
    contradictions: list[str] = Field(max_length=12)
    interpretation_confidence: float = Field(ge=0, le=1)


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
