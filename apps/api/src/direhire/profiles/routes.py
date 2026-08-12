from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.errors import NotFoundError
from direhire.models import CompetencyCatalog, OccupationCatalog, ProfessionalProfile, utcnow

router = APIRouter(tags=["Professional Profile"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


class ProfileCompetency(BaseModel):
    canonical_id: str | None = Field(default=None, max_length=100)
    display_name: str = Field(min_length=1, max_length=160)
    proficiency: int | None = Field(default=None, ge=1, le=5)


class ProfileLanguage(BaseModel):
    language: str = Field(min_length=1, max_length=100)
    proficiency: str | None = Field(default=None, max_length=100)


class EducationEntry(BaseModel):
    qualification: str = Field(min_length=1, max_length=300)
    institution: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1900, le=2200)


class ExperienceEntry(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    company: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=3000)


class Eligibility(BaseModel):
    citizenships: list[str] = Field(default_factory=list, max_length=10)
    authorized_countries: list[str] = Field(default_factory=list, max_length=50)
    sponsorship_needed: Literal["YES", "NO", "PREFER_NOT_TO_SAY", "UNCLEAR"] = "UNCLEAR"


class ProfileWrite(BaseModel):
    headline: str | None = Field(default=None, max_length=300)
    competencies: list[ProfileCompetency] = Field(default_factory=list, max_length=100)
    domain_knowledge: list[str] = Field(default_factory=list, max_length=100)
    technologies_tools: list[str] = Field(default_factory=list, max_length=100)
    languages: list[ProfileLanguage] = Field(default_factory=list, max_length=30)
    credentials_licenses: list[str] = Field(default_factory=list, max_length=50)
    education: list[EducationEntry] = Field(default_factory=list, max_length=30)
    experience: list[ExperienceEntry] = Field(default_factory=list, max_length=100)
    eligibility_work_rights: Eligibility = Field(default_factory=Eligibility)


class ProfileRead(ProfileWrite):
    created_at: datetime
    updated_at: datetime


class CatalogItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    aliases: list[str]


@router.get("/profile", response_model=ProfileRead)
def get_profile(user: User, session: DbSession) -> object:
    profile = session.get(ProfessionalProfile, str(user.id))
    if profile is None:
        raise NotFoundError()
    return profile


@router.put("/profile", response_model=ProfileRead)
def replace_profile(data: ProfileWrite, user: User, session: DbSession) -> object:
    profile = session.get(ProfessionalProfile, str(user.id))
    values = data.model_dump(mode="json")
    if profile is None:
        profile = ProfessionalProfile(user_id=str(user.id), **values)
        session.add(profile)
    else:
        for key, value in values.items():
            setattr(profile, key, value)
        profile.updated_at = utcnow()
    session.commit()
    return profile


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(user: User, session: DbSession) -> Response:
    profile = session.get(ProfessionalProfile, str(user.id))
    if profile is not None:
        session.delete(profile)
        session.commit()
    return Response(status_code=204)


@router.get("/catalog/competencies", response_model=list[CatalogItemRead])
def list_competencies(user: User, session: DbSession, q: str = "") -> object:
    del user
    statement = select(CompetencyCatalog).order_by(CompetencyCatalog.display_name).limit(50)
    if q.strip():
        pattern = f"%{q.strip()[:100]}%"
        statement = statement.where(CompetencyCatalog.display_name.ilike(pattern))
    return list(session.scalars(statement))


@router.get("/catalog/occupations", response_model=list[CatalogItemRead])
def list_occupations(user: User, session: DbSession, q: str = "") -> object:
    del user
    statement = select(OccupationCatalog).order_by(OccupationCatalog.display_name).limit(50)
    if q.strip():
        pattern = f"%{q.strip()[:100]}%"
        statement = statement.where(OccupationCatalog.display_name.ilike(pattern))
    return list(session.scalars(statement))
