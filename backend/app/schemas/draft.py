import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import DraftStatus


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    template_id: uuid.UUID
    template_version: int
    text: str
    edited_text: str | None
    status: DraftStatus
    model_name: str
    reviewer_id: uuid.UUID | None
    reviewed_at: datetime | None
    published_at: datetime | None
    error: str | None
    created_at: datetime


class RegenerateRequest(BaseModel):
    # Draft with this template instead of the source's (e.g. switch to the critical stance).
    template_id: uuid.UUID | None = None


class DraftEdit(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
