import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    created_at: datetime


class RegenerateRequest(BaseModel):
    # Draft with this template instead of the source's (e.g. switch to the critical stance).
    template_id: uuid.UUID | None = None
