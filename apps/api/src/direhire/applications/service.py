from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from direhire.applications.schemas import (
    ApplicationCreate,
    ApplicationUpdate,
    InterviewCreate,
    NoteCreate,
    ReminderCreate,
)
from direhire.errors import ConflictError, NotFoundError
from direhire.models import (
    Application,
    ApplicationNote,
    InterviewRecord,
    Job,
    Reminder,
    UserJob,
    utcnow,
)


class ApplicationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, user_id: str, data: ApplicationCreate) -> dict[str, object]:
        user_job = self.session.scalar(
            select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == data.job_id)
        )
        if user_job is None:
            raise NotFoundError()
        existing = self.session.scalar(
            select(Application).where(
                Application.user_id == user_id, Application.job_id == data.job_id
            )
        )
        if existing is not None:
            return self._read(existing)
        applied_at = data.applied_at
        if data.status == "APPLIED" and applied_at is None:
            applied_at = datetime.now(UTC).date()
        application = Application(
            user_id=user_id,
            job_id=data.job_id,
            status=data.status,
            applied_at=applied_at,
        )
        user_job.status = data.status
        self.session.add(application)
        self.session.commit()
        return self._read(application)

    def list(self, user_id: str) -> list[dict[str, object]]:
        applications = self.session.scalars(
            select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.updated_at.desc())
        )
        return [self._read(application) for application in applications]

    def get(self, application_id: str, user_id: str) -> dict[str, object]:
        return self._read(self._owned(application_id, user_id))

    def update(
        self, application_id: str, user_id: str, data: ApplicationUpdate
    ) -> dict[str, object]:
        application = self._owned(application_id, user_id)
        application.status = data.status
        application.applied_at = data.applied_at
        if data.status == "APPLIED" and application.applied_at is None:
            application.applied_at = datetime.now(UTC).date()
        application.updated_at = utcnow()
        user_job = self.session.scalar(
            select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == application.job_id)
        )
        if user_job is not None:
            user_job.status = data.status
        self.session.commit()
        return self._read(application)

    def delete(self, application_id: str, user_id: str) -> None:
        application = self._owned(application_id, user_id)
        self.session.delete(application)
        self.session.commit()

    def add_note(self, application_id: str, user_id: str, data: NoteCreate) -> ApplicationNote:
        self._owned(application_id, user_id)
        note = ApplicationNote(application_id=application_id, **data.model_dump())
        self.session.add(note)
        self.session.commit()
        return note

    def list_notes(self, application_id: str, user_id: str) -> list[ApplicationNote]:
        self._owned(application_id, user_id)
        return list(
            self.session.scalars(
                select(ApplicationNote)
                .where(ApplicationNote.application_id == application_id)
                .order_by(ApplicationNote.created_at)
            )
        )

    def delete_note(self, application_id: str, note_id: str, user_id: str) -> None:
        self._owned(application_id, user_id)
        deleted = self.session.execute(
            delete(ApplicationNote).where(
                ApplicationNote.id == note_id,
                ApplicationNote.application_id == application_id,
            )
        ).rowcount
        if not deleted:
            raise NotFoundError()
        self.session.commit()

    def add_interview(
        self, application_id: str, user_id: str, data: InterviewCreate
    ) -> InterviewRecord:
        self._owned(application_id, user_id)
        interview = InterviewRecord(application_id=application_id, **data.model_dump())
        self.session.add(interview)
        self.session.commit()
        return interview

    def list_interviews(self, application_id: str, user_id: str) -> list[InterviewRecord]:
        self._owned(application_id, user_id)
        return list(
            self.session.scalars(
                select(InterviewRecord)
                .where(InterviewRecord.application_id == application_id)
                .order_by(InterviewRecord.created_at)
            )
        )

    def add_reminder(self, application_id: str, user_id: str, data: ReminderCreate) -> Reminder:
        self._owned(application_id, user_id)
        reminder = Reminder(application_id=application_id, **data.model_dump())
        self.session.add(reminder)
        self.session.commit()
        return reminder

    def list_reminders(self, application_id: str, user_id: str) -> list[Reminder]:
        self._owned(application_id, user_id)
        return list(
            self.session.scalars(
                select(Reminder)
                .where(Reminder.application_id == application_id)
                .order_by(Reminder.due_at)
            )
        )

    def complete_reminder(self, application_id: str, reminder_id: str, user_id: str) -> Reminder:
        self._owned(application_id, user_id)
        reminder = self.session.scalar(
            select(Reminder).where(
                Reminder.id == reminder_id, Reminder.application_id == application_id
            )
        )
        if reminder is None:
            raise NotFoundError()
        if reminder.completed_at is None:
            reminder.completed_at = utcnow()
            self.session.commit()
        return reminder

    def _owned(self, application_id: str, user_id: str) -> Application:
        application = self.session.scalar(
            select(Application).where(
                Application.id == application_id, Application.user_id == user_id
            )
        )
        if application is None:
            raise NotFoundError()
        return application

    def _read(self, application: Application) -> dict[str, object]:
        job = self.session.get(Job, application.job_id)
        if job is None:
            raise ConflictError("The referenced job is unavailable.")
        return {
            "id": application.id,
            "job_id": application.job_id,
            "title": job.title,
            "company": job.company,
            "status": application.status,
            "applied_at": application.applied_at,
            "created_at": application.created_at,
            "updated_at": application.updated_at,
        }
