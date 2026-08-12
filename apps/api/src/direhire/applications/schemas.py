from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ApplicationStatus = Literal[
    "NEW",
    "VIEWED",
    "SAVED",
    "INTERESTED",
    "APPLIED",
    "INTERVIEWING",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
    "IGNORED",
    "ARCHIVED",
]
InterviewStage = Literal["SCREENING", "TECHNICAL", "FINAL", "OTHER"]
NoteType = Literal["RECRUITER_CALL", "SALARY", "QUESTIONS", "ROLE_DETAILS", "FOLLOW_UP", "OTHER"]
ReminderType = Literal["APPLICATION", "INTERVIEW"]


class ApplicationCreate(BaseModel):
    job_id: str
    status: ApplicationStatus = "APPLIED"
    applied_at: date | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus
    applied_at: date | None = None


class ApplicationRead(BaseModel):
    id: str
    job_id: str
    title: str
    company: str
    status: ApplicationStatus
    applied_at: date | None
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    note_type: NoteType
    body: str = Field(min_length=1, max_length=10_000)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    note_type: NoteType
    body: str
    created_at: datetime
    updated_at: datetime


class InterviewCreate(BaseModel):
    stage: InterviewStage
    scheduled_at: datetime | None = None
    questions_remembered: str | None = Field(default=None, max_length=10_000)
    went_well: str | None = Field(default=None, max_length=10_000)
    difficult: str | None = Field(default=None, max_length=10_000)
    other_notes: str | None = Field(default=None, max_length=10_000)


class InterviewRead(InterviewCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    created_at: datetime
    updated_at: datetime


class ReminderCreate(BaseModel):
    reminder_type: ReminderType
    due_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> "ReminderCreate":
        if self.due_at.tzinfo is None:
            raise ValueError("Reminder time must include a timezone")
        return self


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    reminder_type: ReminderType
    due_at: datetime
    completed_at: datetime | None
    created_at: datetime
