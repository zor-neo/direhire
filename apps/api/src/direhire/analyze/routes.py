from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from direhire.analyze.service import AnalyzeJobService
from direhire.auth import CurrentUser, current_user
from direhire.db import get_session
from direhire.watches.schemas import WatchRead

router = APIRouter(prefix="/analyze-jobs", tags=["Analyze a Job"])
DbSession = Annotated[Session, Depends(get_session)]
User = Annotated[CurrentUser, Depends(current_user)]


class AnalyzeJobRequest(BaseModel):
    input_type: Literal["PUBLIC_URL", "PASTED_TEXT"]
    url: str | None = Field(default=None, max_length=2048)
    text: str | None = Field(default=None, max_length=100_000)

    @model_validator(mode="after")
    def validate_input(self) -> "AnalyzeJobRequest":
        if self.input_type == "PUBLIC_URL" and (not self.url or self.text is not None):
            raise ValueError("PUBLIC_URL requires only url")
        if self.input_type == "PASTED_TEXT" and (not self.text or self.url is not None):
            raise ValueError("PASTED_TEXT requires only text")
        return self


class SimilarOpening(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    source_url: str


class AnalyzeJobRead(BaseModel):
    id: str
    input_type: str
    normalized_url: str | None
    job_id: str | None
    status: str
    analysis: dict[str, object] | None
    similar_openings: list[SimilarOpening]
    saved: bool
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=AnalyzeJobRead, status_code=202)
def request_analysis(
    data: AnalyzeJobRequest,
    request: Request,
    user: User,
    session: DbSession,
) -> object:
    service = AnalyzeJobService(session)
    if data.input_type == "PUBLIC_URL":
        return service.read_model(
            service.request_public(
                str(user.id), user.plan, data.url or "", request.state.correlation_id
            )
        )
    return service.read_model(
        service.request_pasted(
            str(user.id), user.plan, data.text or "", request.state.correlation_id
        )
    )


@router.get("", response_model=list[AnalyzeJobRead])
def list_analyses(user: User, session: DbSession) -> object:
    return AnalyzeJobService(session).list(str(user.id))


@router.get("/{analysis_id}", response_model=AnalyzeJobRead)
def get_analysis(analysis_id: str, user: User, session: DbSession) -> object:
    return AnalyzeJobService(session).get(analysis_id, str(user.id))


@router.post("/{analysis_id}/save", response_model=AnalyzeJobRead)
def save_analysis(analysis_id: str, user: User, session: DbSession) -> object:
    return AnalyzeJobService(session).save(analysis_id, str(user.id))


@router.post("/{analysis_id}/watch-draft", response_model=WatchRead, status_code=201)
def create_watch_draft(analysis_id: str, user: User, session: DbSession) -> object:
    return AnalyzeJobService(session).create_watch(analysis_id, str(user.id))


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: str, user: User, session: DbSession) -> Response:
    AnalyzeJobService(session).delete(analysis_id, str(user.id))
    return Response(status_code=204)
