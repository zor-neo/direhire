from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from direhire.ai.private_service import (
    ArtifactType,
    PrivateAiRequestService,
    ProfileSuggestionService,
    SuggestionEdit,
)
from direhire.auth import CurrentUser, current_user
from direhire.config import Settings, get_settings
from direhire.db import get_session
from direhire.documents.service import TailoredCvService
from direhire.files.storage import PrivateObjectStorage, get_private_storage

router = APIRouter(prefix="/private-ai", tags=["Private AI"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]
Storage = Annotated[PrivateObjectStorage, Depends(get_private_storage)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class ArtifactRequest(BaseModel):
    artifact_type: ArtifactType
    job_id: str | None = Field(default=None, max_length=36)
    cv_id: str | None = Field(default=None, max_length=36)


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_type: str
    job_id: str | None
    cv_id: str | None
    status: str
    content: dict[str, object] | None
    working_draft: dict[str, object] | None
    error_code: str | None
    name: str | None
    version_number: int
    parent_artifact_id: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DraftUpdate(BaseModel):
    working_draft: dict[str, object]


class ArtifactMetadataUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    archived: bool | None = None


class DuplicateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_id: str
    format: Literal["DOCX", "PDF"]
    status: str
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class DocumentDownloadRead(BaseModel):
    url: str
    expires_in_seconds: int


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_id: str
    category: str
    suggestion: dict[str, object]
    status: str
    created_at: datetime
    decided_at: datetime | None


class SuggestionDecision(BaseModel):
    decision: Literal["ACCEPTED", "EDITED", "REJECTED"]
    edit: SuggestionEdit | None = None

    @model_validator(mode="after")
    def validate_edit(self) -> "SuggestionDecision":
        if self.decision == "EDITED" and self.edit is None:
            raise ValueError("edit is required when decision is EDITED")
        return self


@router.post("/artifacts", response_model=ArtifactRead, status_code=202)
def request_artifact(
    data: ArtifactRequest,
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    return PrivateAiRequestService(session).request(
        user_id=str(user.id),
        plan=user.plan,
        artifact_type=data.artifact_type,
        job_id=data.job_id,
        cv_id=data.cv_id,
        correlation_id=request.state.correlation_id,
    )


@router.get("/artifacts", response_model=list[ArtifactRead])
def list_artifacts(user: User, session: DbSession) -> object:
    return PrivateAiRequestService(session).list(str(user.id))


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(artifact_id: str, user: User, session: DbSession) -> object:
    return PrivateAiRequestService(session).get(artifact_id, str(user.id))


@router.patch("/artifacts/{artifact_id}/draft", response_model=ArtifactRead)
def update_artifact_draft(
    artifact_id: str, data: DraftUpdate, user: User, session: DbSession
) -> object:
    return PrivateAiRequestService(session).update_draft(
        artifact_id, str(user.id), data.working_draft
    )


@router.patch("/artifacts/{artifact_id}/metadata", response_model=ArtifactRead)
def update_artifact_metadata(
    artifact_id: str,
    data: ArtifactMetadataUpdate,
    user: User,
    session: DbSession,
) -> object:
    return TailoredCvService(session).update_metadata(
        artifact_id,
        str(user.id),
        name=data.name,
        archived=data.archived,
    )


@router.post("/artifacts/{artifact_id}/duplicate", response_model=ArtifactRead, status_code=201)
def duplicate_artifact(
    artifact_id: str,
    data: DuplicateRequest,
    user: User,
    session: DbSession,
) -> object:
    return TailoredCvService(session).duplicate(artifact_id, str(user.id), data.name)


@router.post(
    "/artifacts/{artifact_id}/documents/{document_format}",
    response_model=DocumentRead,
    status_code=202,
)
def request_document(
    artifact_id: str,
    document_format: Literal["DOCX", "PDF"],
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    return TailoredCvService(session).request_document(
        artifact_id,
        str(user.id),
        document_format,
        request.state.correlation_id,
    )


@router.get("/artifacts/{artifact_id}/documents", response_model=list[DocumentRead])
def list_documents(artifact_id: str, user: User, session: DbSession) -> object:
    return TailoredCvService(session).list_documents(artifact_id, str(user.id))


@router.get("/documents/{document_id}/download", response_model=DocumentDownloadRead)
def download_document(
    document_id: str,
    user: User,
    session: DbSession,
    storage: Storage,
    settings: AppSettings,
) -> object:
    url = TailoredCvService(session).download(document_id, str(user.id), storage, settings)
    return {"url": url, "expires_in_seconds": settings.private_download_url_seconds}


@router.delete("/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artifact(artifact_id: str, user: User, session: DbSession, storage: Storage) -> Response:
    PrivateAiRequestService(session).delete(artifact_id, str(user.id), storage)
    return Response(status_code=204)


@router.get("/profile-suggestions", response_model=list[SuggestionRead])
def list_profile_suggestions(user: User, session: DbSession) -> object:
    return ProfileSuggestionService(session).list(str(user.id))


@router.post("/profile-suggestions/{suggestion_id}/decision", response_model=SuggestionRead)
def decide_profile_suggestion(
    suggestion_id: str,
    data: SuggestionDecision,
    user: User,
    session: DbSession,
) -> object:
    return ProfileSuggestionService(session).decide(
        suggestion_id,
        str(user.id),
        data.decision,
        data.edit,
    )
