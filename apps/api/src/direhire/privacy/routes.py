from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.config import Settings, get_settings
from direhire.db import get_session
from direhire.errors import AppError
from direhire.files.storage import PrivateObjectStorage, get_private_storage
from direhire.privacy.service import PrivacyWorkflowService

router = APIRouter(prefix="/privacy", tags=["Privacy & Data"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
Storage = Annotated[PrivateObjectStorage, Depends(get_private_storage)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    expires_at: datetime | None
    error_code: str | None
    created_at: datetime


class ExportDownloadRead(BaseModel):
    url: str
    expires_in_seconds: int


class DeletionRequest(BaseModel):
    scope: Literal["CAREER_DATA", "ACCOUNT"]
    confirmation: str


class DeletionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: str
    status: str
    error_code: str | None
    progress: dict[str, object]
    created_at: datetime
    completed_at: datetime | None


@router.post("/exports", response_model=ExportRead, status_code=status.HTTP_202_ACCEPTED)
def request_export(
    request: Request,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    return PrivacyWorkflowService(session, storage, settings).request_export(
        str(user.id), request.state.correlation_id
    )


@router.get("/exports", response_model=list[ExportRead])
def list_exports(user: User, session: DbSession, storage: Storage, settings: AppSettings) -> object:
    return PrivacyWorkflowService(session, storage, settings).list_exports(str(user.id))


@router.get("/exports/{export_id}/download", response_model=ExportDownloadRead)
def download_export(
    export_id: str,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    url = PrivacyWorkflowService(session, storage, settings).download_export(
        export_id, str(user.id)
    )
    return {"url": url, "expires_in_seconds": settings.private_download_url_seconds}


@router.post("/deletions", response_model=DeletionRead, status_code=status.HTTP_202_ACCEPTED)
def request_deletion(
    data: DeletionRequest,
    request: Request,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    required = "DELETE MY ACCOUNT" if data.scope == "ACCOUNT" else "DELETE MY CAREER DATA"
    if data.confirmation != required:
        raise AppError("DELETION_CONFIRMATION_INVALID", "Deletion was not confirmed.", 422)
    return PrivacyWorkflowService(session, storage, settings).request_deletion(
        str(user.id), scope=data.scope, correlation_id=request.state.correlation_id
    )


@router.get("/deletions", response_model=list[DeletionRead])
def list_deletions(
    user: User, session: DbSession, storage: Storage, settings: AppSettings
) -> object:
    return PrivacyWorkflowService(session, storage, settings).list_deletions(str(user.id))
