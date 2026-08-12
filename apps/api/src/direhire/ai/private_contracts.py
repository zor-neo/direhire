from typing import Literal

from pydantic import Field

from direhire.ai.contracts import StrictModel


class ProfileSuggestionItem(StrictModel):
    category: Literal["COMPETENCY", "DOMAIN_KNOWLEDGE", "TECHNOLOGY", "LANGUAGE", "CREDENTIAL"]
    display_name: str = Field(min_length=1, max_length=160)
    canonical_id: str | None = Field(default=None, max_length=100)
    proficiency: int | None = Field(default=None, ge=1, le=5)
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class CvProfileSuggestions(StrictModel):
    suggestions: list[ProfileSuggestionItem] = Field(max_length=50)


class ProfileFitResult(StrictModel):
    readiness: Literal["STRONG", "PROMISING", "DEVELOPING", "BLOCKED", "UNCLEAR"]
    summary: str = Field(min_length=1, max_length=1200)
    strengths: list[str] = Field(max_length=15)
    gaps: list[str] = Field(max_length=15)
    blockers: list[str] = Field(max_length=10)
    next_steps: list[str] = Field(max_length=10)


class CvSection(StrictModel):
    heading: str = Field(min_length=1, max_length=120)
    items: list[str] = Field(max_length=30)


class TailoredCvResult(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    professional_summary: str = Field(min_length=1, max_length=1500)
    sections: list[CvSection] = Field(max_length=20)
    omitted_or_deemphasized: list[str] = Field(max_length=15)
    truthfulness_notes: list[str] = Field(max_length=15)


class PrepareToApplyResult(StrictModel):
    checklist: list[str] = Field(max_length=20)
    cover_letter: str = Field(min_length=1, max_length=8000)
    application_message: str = Field(min_length=1, max_length=2000)
    recruiter_message: str = Field(min_length=1, max_length=2000)


class CareerPrepResult(StrictModel):
    likely_questions: list[str] = Field(max_length=20)
    grounded_scenarios: list[str] = Field(max_length=10)
    preparation_actions: list[str] = Field(max_length=15)
    uncertainty_notes: list[str] = Field(max_length=10)


class CompanyResearchResult(StrictModel):
    employer_facts_from_job: list[str] = Field(max_length=15)
    role_context: list[str] = Field(max_length=15)
    questions_to_verify: list[str] = Field(max_length=15)
    research_actions: list[str] = Field(max_length=15)
    limitations: list[str] = Field(max_length=10)


class ProfessionalAdviceResult(StrictModel):
    priorities: list[str] = Field(max_length=15)
    evidence: list[str] = Field(max_length=15)
    do_not_spend_time_on: list[str] = Field(max_length=15)
    caveats: list[str] = Field(max_length=10)
