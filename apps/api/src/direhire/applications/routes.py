from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from direhire.applications.schemas import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    InterviewCreate,
    InterviewRead,
    NoteCreate,
    NoteRead,
    ReminderCreate,
    ReminderRead,
)
from direhire.applications.service import ApplicationService
from direhire.auth import CurrentUser, current_user
from direhire.db import get_session

router = APIRouter(prefix="/applications", tags=["Applications"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate, user: User, session: DbSession) -> object:
    return ApplicationService(session).create(str(user.id), data)


@router.get("", response_model=list[ApplicationRead])
def list_applications(user: User, session: DbSession) -> object:
    return ApplicationService(session).list(str(user.id))


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(application_id: str, user: User, session: DbSession) -> object:
    return ApplicationService(session).get(application_id, str(user.id))


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: str, data: ApplicationUpdate, user: User, session: DbSession
) -> object:
    return ApplicationService(session).update(application_id, str(user.id), data)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: str, user: User, session: DbSession) -> Response:
    ApplicationService(session).delete(application_id, str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{application_id}/notes", response_model=NoteRead, status_code=201)
def add_note(application_id: str, data: NoteCreate, user: User, session: DbSession) -> object:
    return ApplicationService(session).add_note(application_id, str(user.id), data)


@router.get("/{application_id}/notes", response_model=list[NoteRead])
def list_notes(application_id: str, user: User, session: DbSession) -> object:
    return ApplicationService(session).list_notes(application_id, str(user.id))


@router.delete("/{application_id}/notes/{note_id}", status_code=204)
def delete_note(application_id: str, note_id: str, user: User, session: DbSession) -> Response:
    ApplicationService(session).delete_note(application_id, note_id, str(user.id))
    return Response(status_code=204)


@router.post("/{application_id}/interviews", response_model=InterviewRead, status_code=201)
def add_interview(
    application_id: str, data: InterviewCreate, user: User, session: DbSession
) -> object:
    return ApplicationService(session).add_interview(application_id, str(user.id), data)


@router.get("/{application_id}/interviews", response_model=list[InterviewRead])
def list_interviews(application_id: str, user: User, session: DbSession) -> object:
    return ApplicationService(session).list_interviews(application_id, str(user.id))


@router.post("/{application_id}/reminders", response_model=ReminderRead, status_code=201)
def add_reminder(
    application_id: str, data: ReminderCreate, user: User, session: DbSession
) -> object:
    return ApplicationService(session).add_reminder(application_id, str(user.id), data)


@router.get("/{application_id}/reminders", response_model=list[ReminderRead])
def list_reminders(application_id: str, user: User, session: DbSession) -> object:
    return ApplicationService(session).list_reminders(application_id, str(user.id))


@router.post("/{application_id}/reminders/{reminder_id}/complete", response_model=ReminderRead)
def complete_reminder(
    application_id: str, reminder_id: str, user: User, session: DbSession
) -> object:
    return ApplicationService(session).complete_reminder(application_id, reminder_id, str(user.id))
