import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Platform, SourceStance


class SourceCreate(BaseModel):
    platform: Platform
    display_name: str = Field(min_length=1, max_length=200)
    url_or_handle: str = Field(min_length=1, max_length=2000)
    # Defaults to the platform's adapter (see source_service.DEFAULT_ADAPTERS).
    adapter: str | None = Field(default=None, max_length=50)
    prompt_template_id: uuid.UUID | None = None
    stance: SourceStance = SourceStance.neutral
    poll_interval_minutes: int = Field(default=15, ge=1, le=1440)
    is_active: bool = True


class SourceUpdate(BaseModel):
    platform: Platform | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    url_or_handle: str | None = Field(default=None, min_length=1, max_length=2000)
    adapter: str | None = Field(default=None, max_length=50)
    prompt_template_id: uuid.UUID | None = None
    stance: SourceStance | None = None
    poll_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    is_active: bool | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    display_name: str
    url_or_handle: str
    adapter: str
    prompt_template_id: uuid.UUID | None
    stance: SourceStance
    poll_interval_minutes: int
    is_active: bool
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PollQueued(BaseModel):
    queued: bool  # False when a poll for this source was already waiting in the queue
