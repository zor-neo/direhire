from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from direhire.auth import CurrentUser, current_user
from direhire.config import Settings, get_settings
from direhire.db import get_session
from direhire.files.service import CvService
from direhire.files.storage import PrivateObjectStorage, get_private_storage

router = APIRouter(prefix="/cvs", tags=["CVs"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
Storage = Annotated[PrivateObjectStorage, Depends(get_private_storage)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class CvUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(max_length=100)
    size: int


class CvRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str


class CvUploadRead(CvRead):
    upload_url: str
    upload_fields: dict[str, str]


class DownloadRead(BaseModel):
    url: str
    expires_in_seconds: int


@router.post("/uploads", response_model=CvUploadRead, status_code=201)
def initiate_cv_upload(
    data: CvUploadRequest,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    cv, _, upload = CvService(session, storage, settings).initiate_upload(
        user_id=str(user.id),
        plan=user.plan,
        name=data.name,
        filename=data.filename,
        content_type=data.content_type,
        size=data.size,
    )
    return {
        "id": cv.id,
        "name": cv.name,
        "status": cv.status,
        "upload_url": upload.url,
        "upload_fields": upload.fields,
    }


@router.post("/{cv_id}/complete", response_model=CvRead)
def complete_cv_upload(
    cv_id: str,
    request: Request,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    return CvService(session, storage, settings).complete_upload(
        cv_id, str(user.id), request.state.correlation_id
    )


@router.get("", response_model=list[CvRead])
def list_cvs(user: User, session: DbSession, storage: Storage, settings: AppSettings) -> object:
    return CvService(session, storage, settings).list(str(user.id))


@router.get("/{cv_id}/download", response_model=DownloadRead)
def download_cv(
    cv_id: str,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    url = CvService(session, storage, settings).download(cv_id, str(user.id))
    return {"url": url, "expires_in_seconds": settings.private_download_url_seconds}


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv(
    cv_id: str,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> Response:
    CvService(session, storage, settings).delete(cv_id, str(user.id))
    return Response(status_code=204)
